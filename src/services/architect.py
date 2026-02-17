"""
Architect service - Plans simulation configuration.

Orchestrates:
1. Knowledge service → understand physics requirements
2. Cases service → find best baseline example
3. Generate modification plan → what needs to change

Output: Structured plan for input_writer to execute
"""

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from database.configs.registry import (
    get_cfl_param_name,
    get_chemistry_param_keys,
    get_low_mach_solver,
    get_reaction_flag_keys,
    get_solver_match_exclusions,
    get_solver_ode_tolerance_plan,
)
from pydantic import BaseModel

from src.services.cases import AMReXCasesService
from src.services.config_model_factory import ConfigModelFactory
from src.services.knowledge import PeleKnowledgeService
from src.services.plan import SimulationPlan, SimulationPlanFactory
from database.indexing.level2_constants import LEVEL2_BASE_KEYS


class ParameterModification(BaseModel):
    """Parameter modification extracted from a plan."""

    parameter: str
    value: str
    reason: str

class ModificationExtraction(BaseModel):
    """Structured container for extracted modifications."""

    modifications: list[ParameterModification]

logger = logging.getLogger(__name__)



@dataclass
class LLMPlanResult:
    """Result from LLM-based planning."""

    modifications: list[tuple[str, str]]  # List of (parameter, value) tuples
    reasoning: str


@dataclass
class SolverSelection:
    """Wrapper that behaves like a config while supporting tuple unpacking."""

    config: Any
    confidence: float

    def __iter__(self):
        yield self.config
        yield self.confidence

    @property
    def code_name(self) -> str | None:
        """
        Return the solver code name if present.

        Parameters
        ----------
        None

        Returns
        -------
        str or None
            Code name from the wrapped config, if available.
        """
        return getattr(self.config, "code_name", None)

    def __getattr__(self, name: str):
        return getattr(self.config, name)


class ArchitectService:
    """Plans simulation configuration from natural language prompt.

    Workflow:
    1. Parse user prompt → extract key requirements
    2. Query knowledge base → understand physics
    3. Find baseline case → best starting point
    4. Plan modifications → grid, timestep, chemistry, etc.

    Example:
        >>> architect = ArchitectService(config)
        >>> plan = architect.create_plan(
        ...     "2D hydrogen flame, 512x512 grid, AMR with 2 levels"
        ... )
        >>> print(plan['baseline'])  # Best example to start from
        >>> print(plan['modifications'])  # What to change
    """

    def __init__(self, config, embedding_service=None):
        self.config = config
        self.embedder = embedding_service
        self._knowledge = None

        # Initialize Level 0 Searcher (Architect Service: Solver Selection)
        if embedding_service and hasattr(config, "faiss_db_path"):
            from database.indexing.level0_searcher import Level0Searcher
            self.level0_searcher = Level0Searcher(
                index_dir=config.faiss_db_path / "level0",
                embedder=self.embedder
            )
        else:
            self.level0_searcher = None

        # Initialize Level 2 Searcher placeholder
        self.level2_searcher = None

        # Initialize Config Registry (Cases Service: Config-Driven Discovery)
        from database.configs import discover_code_configs
        self.code_configs = {cfg.code_name: cfg for cfg in discover_code_configs()}
        self.cases = AMReXCasesService(config)

        # Initialize LLM client for hierarchical planning
        from src.config import get_llm_client
        try:
            self.llm_client = get_llm_client(config)
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {e}")
            self.llm_client = None

        # Initialize FAISS embedding service for semantic search (5th scoring bucket)
        if embedding_service is not None:
            self.embeddings = embedding_service
        else:
            try:
                from .embedding import EmbeddingService
                self.embeddings = EmbeddingService(config)
            except Exception as e:
                logger.debug(f"Warning: Could not initialize FAISS embeddings: {e}")
                self.embeddings = None

    @property
    def knowledge(self) -> PeleKnowledgeService:
        if self._knowledge is None:
            self._knowledge = PeleKnowledgeService(self.config)
        return self._knowledge

    def _schema_has_param(self, solver_name: str | None, param_name: str) -> bool:
        if not solver_name:
            return False
        solver_config = self.code_configs.get(solver_name)
        if not solver_config:
            return False
        try:
            schema_path = ConfigModelFactory.resolve_schema_path(
                solver_config,
                self.config.amrex_agent_root / "database/schemas",
                self.config.amrex_agent_root,
            )
            schema = ConfigModelFactory.load_schema(schema_path)
        except Exception as exc:
            logger.debug(f"Could not load schema for {solver_name}: {exc}")
            return False
        return param_name in schema

    def _load_schema_details(self, solver_config) -> dict[str, Any]:
        try:
            schema_path = ConfigModelFactory.resolve_schema_path(
                solver_config,
                self.config.amrex_agent_root / "database/schemas",
                self.config.amrex_agent_root,
            )
            schema = ConfigModelFactory.load_schema(schema_path)
            if isinstance(schema, dict) and "parameters" in schema:
                schema = schema.get("parameters", {})
            if isinstance(schema, dict):
                return schema
        except Exception as exc:
            logger.debug(f"Could not load schema details: {exc}")
        return {}

    @staticmethod
    def _param_keywords(param_name: str, description: str | None) -> set[str]:
        tokens = set(re.split(r'[^a-zA-Z0-9]+', param_name.lower()))
        if description:
            tokens.update(re.split(r'[^a-zA-Z0-9]+', description.lower()))
        stop = {"", "amr", "max", "min", "plot", "check", "file", "files"}
        keywords = {t for t in tokens if len(t) >= 3 and t not in stop and not t.isdigit()}
        expanded = set()
        for token in keywords:
            expanded.add(token)
            if token == "step":
                expanded.update({"steps", "timestep", "timesteps"})
            if token == "cell":
                expanded.add("cells")
        return expanded

    def _get_tier_params(
        self,
        solver_config,
        available_params: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        from database.configs.base_amrex_config import BaseAMReXConfig

        tier1 = set(BaseAMReXConfig.tier1_params)
        tier2 = set(BaseAMReXConfig.tier2_params)
        if solver_config:
            tier1.update(getattr(solver_config, "tier1_params", set()) or set())
            tier2.update(getattr(solver_config, "tier2_params", set()) or set())

        if available_params:
            available_set = set(available_params)
            tier1 = {name for name in tier1 if name in available_set}
            tier2 = {name for name in tier2 if name in available_set}

        return sorted(tier1), sorted(tier2)

    def _extract_tier1_overrides(
        self,
        prompt: str,
        solver_name: str | None,
        solver_config,
    ) -> list[tuple[str, str]]:
        if not solver_config:
            return []

        schema = self._load_schema_details(solver_config)
        available_params = sorted(schema.keys())
        tier1_params, _tier2_params = self._get_tier_params(
            solver_config, available_params
        )

        prompt_lower = prompt.lower()
        overrides: list[tuple[str, str]] = []

        for param in tier1_params:
            param_info = schema.get(param)
            if not param_info:
                continue

            param_pattern = re.escape(param)
            explicit = re.search(
                rf"\b{param_pattern}\s*=\s*([0-9eE+\-.\s]+)",
                prompt,
            )
            if explicit:
                value = explicit.group(1).strip()
                if value:
                    overrides.append((param, value))
                continue

            description = param_info.get("description")
            keywords = self._param_keywords(param, description)
            if not keywords:
                continue

            for keyword in keywords:
                match = re.search(rf"(\d+(?:\.\d+)?)\s*{re.escape(keyword)}\b", prompt_lower)
                if match:
                    overrides.append((param, match.group(1)))
                    break

        return overrides

    @staticmethod
    def _resolve_llm_prompt_template(solver_config, template_name: str) -> str:
        from database.configs.base_amrex_config import BaseAMReXConfig

        templates = BaseAMReXConfig.get_prompt_templates().get("architect", {})
        if solver_config:
            templates = solver_config.get_prompt_templates().get(
                "architect", templates
            )
        return templates[template_name]

    def select_solver(self, query: str, confidence_threshold: float = 0.15) -> tuple:
        """
        Identify the correct solver using Level 0 RAG with LLM fallback.

        Call context: Used by the Architect node to select a solver.

        Parameters
        ----------
        query : str
            User requirement string.
        confidence_threshold : float, optional
            Minimum confidence to trust vector search.

        Returns
        -------
        tuple
            Tuple of (config_class, confidence_score).
        """
        if not self.level0_searcher:
            logger.warning("Level0Searcher not initialized")
            return SolverSelection(None, 0.0)

        # Query Level 0 index
        logger.debug(f" Level0 searching for: '{query}'")
        results = self.level0_searcher.search(query, top_k=1)

        logger.debug(f" Level0 results: {[(r['code'], r['score']) for r in results]}")

        if not results:
            logger.error("No solver found for query: %s", query)
            return SolverSelection(None, 0.0)

        best_match = results[0]
        code_name = best_match["code"]
        confidence = best_match["score"]

        logger.info("Selected solver: %s (confidence: %.2f)", code_name, confidence)

        # LLM fallback for low-confidence results
        if confidence < confidence_threshold:
            logger.warning(f"Low confidence ({confidence:.2f} < {confidence_threshold})")
            if self.llm_client:
                logger.info("Falling back to LLM-based solver selection")
                try:
                    # Use LLM to select solver (returns tuple: (code_name, case_path))
                    llm_code_name, _ = self.cases.find_best_match(query, self.llm_client)
                    logger.info(f"LLM selected solver: {llm_code_name}")
                    code_name = llm_code_name
                    # Set confidence to 0.8 for LLM-based selection (heuristic-based)
                    confidence = 0.8
                except Exception as e:
                    logger.warning(f"LLM fallback failed: {e}. Using vector search result.")
            else:
                logger.warning("No LLM client available for fallback. Using low-confidence result.")

        # Map to Config class
        if code_name in self.code_configs:
            return SolverSelection(self.code_configs[code_name], confidence)

        raise ValueError(f"Solver {code_name} found in index but not in registry")

    def retrieve_context(self, query: str, solver_config) -> list:
        """
        Level 1: Retrieve technical documentation for selected solver.

        Call context: Used by Architect planning to gather RAG context.

        Parameters
        ----------
        query : str
            User prompt.
        solver_config : object
            Config from Level 0 (e.g., BaseAMReXConfig subclass).

        Returns
        -------
        list
            Top relevant document snippets with metadata.
        """
        from database.indexing.level1_searcher import Level1Searcher

        solver_name = solver_config.code_name

        # Instantiate Level 1 Searcher for this solver
        index_dir = self.config.faiss_db_path / "level1"

        searcher = Level1Searcher(
            code=solver_name,
            index_dir=index_dir,
            embedder=self.embedder
        )

        # Execute search (FR-3: search all 7 doc indices)
        results = searcher.search_all_docs(query, top_k=5)

        logger.debug(
            "Retrieved %d context documents for %s",
            len(results),
            solver_name
        )

        return results

    def select_baseline(self, query: str, solver_config, excluded_cases: list = None) -> dict:
        """
        Level 2: Select specific baseline case using 7 weighted indices.

        This is the Architect Service: Baseline Selection implementation using RAG-based search.
        Replaces the legacy _select_baseline() 5-bucket heuristic.

        Call context: Used by Architect planning to pick a starting case.

        Parameters
        ----------
        query : str
            User prompt.
        solver_config : object
            Config from Level 0 (e.g., BaseAMReXConfig subclass).
        excluded_cases : list, optional
            Cases to exclude from selection.

        Returns
        -------
        dict
            Selection payload with selected_case, candidates, and confidence.
        """
        from database.indexing.level2_searcher import Level2Searcher

        solver_name = solver_config.code_name

        # Initialize Level 2 Searcher for this solver
        index_dir = self.config.faiss_db_path / "level2"

        searcher = Level2Searcher(
            code=solver_name,
            index_dir=index_dir,
            embedder=self.embedder
        )

        # Execute weighted search
        # Weights from Indexing Engine: Physics-Agnostic Keywords & Scoring:
        #   Physics(30%), Grid(20%), Path(15%), Dev(10%),
        #   Complex(10%), Domain(10%), Resource(5%)
        candidates = searcher.search_all_cases(query, top_k=5)
        candidates = sorted(
            candidates,
            key=lambda c: c.get("score", 0.0),
            reverse=True,
        )

        if not candidates:
            logger.warning("No baseline cases found for %s", solver_name)
            return None

        # Filter excluded cases
        excluded_cases = excluded_cases or []
        if excluded_cases:
            logger.debug(f"Filtering {len(excluded_cases)} excluded cases: {excluded_cases}")
            candidates = [
                c for c in candidates
                if c.get('case') not in excluded_cases
                and c.get('metadata', {}).get('repo_path') not in excluded_cases
            ]

            if not candidates:
                logger.warning("No candidates remaining after exclusion filter")
                return None

        selected = candidates[0]  # Top ranked

        logger.info(
            "Selected baseline: %s (score: %.2f)",
            selected["case"],
            selected["score"]
        )

        return {
            "selected_case": selected,
            "candidates": candidates,
            "confidence": selected["score"]
        }

    def plan_modifications(self, query: str, baseline: dict, solver_code: str = None, parameter_resolution_feedback: dict[str, Any] = None) -> dict:
        """
        Generate modifications using Level 2 indices (parameter-level retrieval).

        Flow:
        1. Level 2 search: query → parameter patterns (grid/chemistry/physics)
        2. Extract modifications from matched cases
        3. (Interactive) Show evidence and get approval

        Call context: Used by Architect planning to propose input changes.

        Parameters
        ----------
        query : str
            User prompt.
        baseline : dict
            Selected baseline case (from Level 1).
        solver_code : str or None, optional
            Solver identifier override.
        parameter_resolution_feedback : dict or None, optional
            Feedback payload for parameter resolution.

        Returns
        -------
        dict
            Modifications payload with evidence and confidence.
        """
        from database.indexing.level2_searcher import Level2Searcher

        modifications = []
        evidence = []
        solver_config = None
        if solver_code:
            solver_config = self.code_configs.get(solver_code)
        else:
            baseline_solver = baseline.get('metadata', {}).get('solver') or baseline.get('metadata', {}).get('code')
            if baseline_solver:
                solver_config = self.code_configs.get(baseline_solver)

        # Initialize Level2Searcher
        if not hasattr(self, 'level2_searcher') or self.level2_searcher is None:
            solver_name = solver_code or baseline.get('metadata', {}).get('solver')
            if not solver_name:
                raise ValueError("Cannot determine solver: missing from baseline metadata and no solver_code provided")
            logger.debug(f"[Level2] Using solver: {solver_name}")
            index_dir = self.config.faiss_db_path / "level2"
            self.level2_searcher = Level2Searcher(
                code=solver_name,
                index_dir=index_dir,
                embedder=self.embedder
            )

        baseline_content = baseline.get('metadata', {}).get('inputs_content', {})
        baseline_case = baseline.get('case', 'unknown')

        logger.debug(f"[Level2] Searching for parameter patterns matching: {query}")

        # Search Level 2 indices
        matches = self.level2_searcher.search_all_cases(query, top_k=3)

        if not matches:
            logger.info("[Level2] No matches - falling back to LLM extraction")
            inputs_content = baseline.get('metadata', {}).get('inputs_content', {})
            llm_result = self.extract_physics_modifications(
                query,
                inputs_content,
                parameter_resolution_feedback=parameter_resolution_feedback,
                solver_config=solver_config,
            )
            llm_result["similar_cases"] = [baseline_case]
            return llm_result

        # Extract modifications from top matches
        for match in matches:
            case_name = (
                match.get("case")
                or match.get("metadata", {}).get("repo_path")
                or "unknown"
            )
            target_content = match.get('metadata', {}).get('inputs_content', {})

            if not target_content:
                logger.debug(f"[Level2] {case_name} missing inputs_content")
                continue

            # Calculate diff: baseline → target
            diff = self._calculate_diff(baseline_content, target_content)

            if diff:
                logger.debug(f"[Level2] Found {len(diff)} modifications from {case_name}")
                modifications.extend(diff)
                evidence.append(case_name)

        # Remove duplicates
        modifications = list(dict.fromkeys(modifications))

        # Interactive approval
        #if getattr(self.config, 'interactive', False) and modifications:
        #    modifications = self._interactive_approve_modifications(
        #        modifications, baseline_content, evidence
        #    )
        if len(modifications) < 2:
            logger.info("[Level2] Sparse retrieval - augmenting with LLM extraction")
            inputs_content = baseline.get('metadata', {}).get('inputs_content', {})
            llm_result = self.extract_physics_modifications(
                query,
                inputs_content,
                parameter_resolution_feedback=parameter_resolution_feedback,
                solver_config=solver_config,
            )
            modifications.extend(llm_result.get('modifications', []))
            modifications = list(dict.fromkeys(modifications))
        logger.debug(f"[Level2] Returning {len(modifications)} modifications")

        return {
            "modifications": modifications,
            "similar_cases": evidence,
            "confidence": 1.0 if modifications else 0.5,
            "used_llm": False  # Pure retrieval from Level 2
        }

    def _interactive_approve_modifications(self, mods: list, baseline: dict, evidence: list) -> list:
        """Show Level 2 evidence and get user approval."""
        logger.info("\n" + "=" * 70)
        logger.info("LEVEL 2: PARAMETER PATTERNS")
        logger.info("=" * 70)
        logger.info(f"\nFound {len(mods)} modifications from {len(evidence)} similar cases:")
        logger.info(f"Evidence: {', '.join(evidence[:3])}")

        logger.info("\nProposed changes:")
        for i, (param, value) in enumerate(mods, 1):
            old = baseline.get(param, '<not set>')
            logger.info(f"  {i:2d}. {param:40s}")
            logger.info(f"      {old} -> {value}")

        logger.info("\n" + "=" * 70)
        choice = input("Accept? [Y/n/s=select specific]: ").strip().lower()

        if choice == 'n':
            return []

        elif choice == 's':
            # Let user cherry-pick
            selected = []
            for i, mod in enumerate(mods, 1):
                keep = input(f"  Keep #{i} ({mod[0]})? [y/N]: ").strip().lower()
                if keep == 'y':
                    selected.append(mod)
            return selected

        return mods

    def execute_planning(
        self,
        user_prompt: str,
        baseline_override: str | None = None,
        strategy: str | None = None,
        **kwargs
    ) -> SimulationPlan:
        """
        Execute planning with the configured strategy and return a plan.

        Call context: Primary entry point used by the Architect node.

        Parameters
        ----------
        user_prompt : str
            User's natural language requirement.
        baseline_override : str or None, optional
            Explicit baseline path override.
        strategy : str or None, optional
            Strategy name ("hierarchical", "simple", or "override_static").
        **kwargs : dict
            Additional planning options (exclusions, weights, feedback).

        Returns
        -------
        SimulationPlan
            Structured plan describing solver, baseline, and modifications.
        """
        # Resolve strategy (explicit param > config > default)
        if strategy is None:
            strategy = getattr(self.config, 'indexing_strategy', 'hierarchical')

        # Resolve baseline_override (explicit param > config > None)
        if baseline_override is None:
            baseline_override = getattr(self.config, 'baseline_override', None)

        logger.info(f"Using indexing strategy: {strategy}")

        if strategy == "override_static" and not baseline_override:
            raise ValueError("override_static strategy requires baseline_override to be set")

        # === BASELINE OVERRIDE PATH ===
        if baseline_override:
            logger.info(f"Baseline override detected: {baseline_override}")
            return self._execute_planning_with_override(
                user_prompt=user_prompt,
                baseline_override=baseline_override,
                strategy=strategy,
                **kwargs
            )

        # === NORMAL PATH (No override) ===
        if strategy == "hierarchical":
            try:
                # Extract hierarchical-specific kwargs
                excluded_cases = kwargs.get('excluded_cases', [])
                excluded_inputs_files = kwargs.get('excluded_inputs_files', [])
                parameter_resolution_feedback = kwargs.get('parameter_resolution_feedback')

                plan = self.create_plan_rag(
                    user_prompt=user_prompt,
                    excluded_cases=excluded_cases,
                    excluded_inputs_files=excluded_inputs_files,
                    parameter_resolution_feedback=parameter_resolution_feedback
                )
                logger.debug("Hierarchical indexing succeeded")
                return plan
            except Exception as e:
                logger.exception("Hierarchical indexing failed: %s", e)
                if getattr(self.config, 'fallback_to_simple_on_error', True):
                    logger.debug("Falling back to simple indexing")
                    strategy = "simple"
                else:
                    raise

        # Simple strategy
        plan = self.create_plan(user_prompt=user_prompt, **kwargs)
        logger.debug("Simple indexing succeeded")
        return plan


    def _execute_planning_with_override(
        self,
        user_prompt: str,
        baseline_override: str,
        strategy: str,
        **kwargs
    ) -> SimulationPlan:
        """
        Execute planning with baseline override (0 modifications).

        Critical constraints:
        - selected_solver MUST match baseline['code_name']
        - baseline['local_path'] MUST exist
        - modifications MUST be empty (user wants exact baseline)

        Args:
            user_prompt: User's request
            baseline_override: Baseline path (e.g., '<repo_name>/Exec/<problem_directory>')
            strategy: 'simple' or 'hierarchical'

        Returns
        -------
            SimulationPlan with overridden baseline and 0 modifications
        """
        parameter_resolution_feedback = kwargs.get("parameter_resolution_feedback")
        # === Step 1: Parse baseline override ===
        baseline_info = self._parse_baseline_override(baseline_override)

        code_name = baseline_info['code_name']
        case_path = baseline_info['case_path']
        repo_path = baseline_info['repo_path']
        local_path = baseline_info['local_path']

        logger.debug(f"[Override] Parsed: {code_name}/{case_path}")
        logger.debug(f"[Override] Local path: {local_path}")

        # === Step 2: Validate local path exists ===
        if not local_path.exists():
            raise ValueError(
                f"Baseline override path does not exist: {local_path}\n"
                f"Expected: {repo_path}/{case_path}"
            )

        # === Step 3: Build baseline result dict ===
        baseline_result = {
            'selected_case': {
                'case': case_path,
                'metadata': {
                    'code': code_name,
                    'path': case_path,
                    'name': f"{code_name}/{case_path}",
                    'local_path': str(local_path),
                    'repo_path': str(repo_path)
                }
            },
            'confidence': 1.0,
            'candidates': [],
            'override': True
        }

        # === Step 4: Strategy-specific handling ===
        if strategy == "override_static":
            return self._override_static(
                user_prompt,
                code_name,
                baseline_result,
                case_path,
                local_path,
                repo_path,
                parameter_resolution_feedback,
            )
        if strategy == "hierarchical":
            return self._override_hierarchical(
                user_prompt, code_name, baseline_result, **kwargs
            )
        else:
            return self._override_simple(
                user_prompt,
                code_name,
                baseline_result,
                case_path,
                local_path,
                repo_path,
                parameter_resolution_feedback,
            )


    def _parse_baseline_override(self, baseline_override: str) -> dict:
        """
        Parse baseline override into components.

        Supported formats:
        - "<repo_name>/Exec/<problem_directory>" → code + case
        - "Exec/<problem_directory>" → invalid (code prefix required)

        Args:
            baseline_override: Override string

        Returns
        -------
            Dict with code_name, case_path, repo_path, local_path

        Raises
        ------
            ValueError: If code not configured or path invalid
        """
        from pathlib import Path

        # Split on first /
        parts = baseline_override.split('/')

        # Check if first part is a known code
        code_registry = self.config.get_code_registry()
        code_lookup = {key.lower(): key for key in code_registry}
        code_key = parts[0].lower()
        if code_key in code_lookup:
            code_name = code_lookup[code_key]
            case_path = '/'.join(parts[1:])
        else:
            # No code prefix → require explicit solver
            raise ValueError(
                f"Baseline override '{baseline_override}' missing code prefix. "
                f"Use format: 'SolverName/Path'. Available: {list(code_registry.keys())}"
            )

        # Get repo path from config
        repo_attr = f'{code_name.lower()}_repo_path'
        repo_path = getattr(self.config, repo_attr, None)

        if not repo_path:
            raise ValueError(
                f"Repository path not configured for {code_name}.\n"
                f"Expected config attribute: {repo_attr}"
            )

        repo_path = Path(repo_path)
        local_path = repo_path / case_path

        return {
            'code_name': code_name,
            'case_path': case_path,
            'repo_path': repo_path,
            'local_path': local_path
        }

    def _ensure_baseline_inputs_content(
        self,
        baseline_result: dict,
        solver_config,
        default_local_path: Path | None = None,
        default_repo_path: Path | None = None,
    ) -> None:
        """Ensure baseline inputs_content is populated for modification planning."""
        if not baseline_result or not solver_config:
            return

        selected_case = baseline_result.get("selected_case", {})
        metadata = selected_case.setdefault("metadata", {})
        if metadata.get("inputs_content"):
            return

        local_path = metadata.get("local_path") or selected_case.get("local_path")
        repo_path = metadata.get("repo_path") or selected_case.get("repo_path")
        if not local_path and default_local_path:
            local_path = str(default_local_path)
        if not repo_path and default_repo_path:
            repo_path = str(default_repo_path)

        if not local_path:
            return

        local_path_obj = Path(local_path)
        if not local_path_obj.exists():
            return

        try:
            metadata_from_inputs = solver_config.extract_metadata(
                local_path_obj,
                repo_root=Path(repo_path) if repo_path else None,
            )
        except Exception as exc:
            logger.debug(f"[Baseline] extract_metadata failed: {exc}")
            return

        inputs_content = metadata_from_inputs.get("inputs_content", {})
        if inputs_content:
            metadata["inputs_content"] = inputs_content


    def _override_hierarchical(
        self,
        user_prompt: str,
        code_name: str,
        baseline_result: dict,
        **kwargs
    ) -> SimulationPlan:
        """
        Hierarchical strategy with override.

        Flow:
        1. (Optional) Run L0 for validation, but ignore result
        2. Retrieve context (L1) using override solver
        3. Skip L2 (baseline already specified)
        4. Skip L3 (0 modifications for override)
        5. Return plan with override baseline
        """
        # Get solver config for override code
        if code_name not in self.code_configs:
            raise ValueError(f"No config found for override solver {code_name}")

        solver_config = self.code_configs[code_name]
        parameter_resolution_feedback = kwargs.get('parameter_resolution_feedback')

        self._ensure_baseline_inputs_content(
            baseline_result=baseline_result,
            solver_config=solver_config,
        )

        # Optional: Validate with L0 (log warning if mismatch)
        if self.level0_searcher:
            try:
                detected_config, detected_conf = self.select_solver(user_prompt)
                if detected_config and detected_config.code_name != code_name:
                    logger.warning(
                        f"[Override] L0 detected {detected_config.code_name} "
                        f"but override specifies {code_name}. Using override."
                    )
            except Exception as e:
                logger.debug(f"[Override] L0 validation skipped: {e}")

        # Retrieve context (L1) using override solver
        docs = self.retrieve_context(user_prompt, solver_config)
        logger.debug(f"[Override] Retrieved {len(docs)} docs for {code_name}")

        # Extract modifications from user prompt against baseline
        case_path = baseline_result['selected_case']['case']
        inputs_content = baseline_result['selected_case'].get('metadata', {}).get('inputs_content', {})

        cbr_plan = self.extract_physics_modifications(
            user_prompt,
            inputs_content,
            parameter_resolution_feedback=parameter_resolution_feedback,
            solver_config=solver_config,
        )
        cbr_plan['baseline_case'] = case_path
        cbr_plan['override'] = True

        logger.debug(f"[Override] Extracted {len(cbr_plan.get('modifications', []))} modifications")

        # Build plan using factory
        return SimulationPlanFactory.create_from_rag(
            solver_name=code_name,
            baseline_result=baseline_result,
            cbr_plan=cbr_plan,
            docs=docs,
            user_prompt=user_prompt,
            solver_confidence=1.0,  # Override = 100% confidence
            used_llm=False
        )

    def _collect_static_docs(self, solver_config, repo_path: Path, limit: int = 10) -> list[dict[str, Any]]:
        """Collect documentation chunks without embeddings."""
        doc_map = getattr(solver_config, "documentation_map", {}) or {}
        if not doc_map:
            return []

        docs: list[dict[str, Any]] = []

        def _read_document(file_path: Path) -> str | None:
            try:
                return file_path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.debug(f"[Override] Could not read {file_path}: {exc}")
                return None

        def _chunk_document(content: str) -> list[dict[str, Any]]:
            chunks: list[dict[str, Any]] = []
            if "##" in content:
                sections = content.split("\n## ")
                for i, section in enumerate(sections):
                    if i == 0:
                        if section.strip():
                            chunks.append({"text": section.strip(), "metadata": {"section": "header"}})
                    else:
                        lines = section.split("\n")
                        title = lines[0]
                        body = "\n".join(lines[1:])
                        if body.strip():
                            chunks.append({
                                "text": f"{title}\n{body}",
                                "metadata": {"section": title, "category": title},
                            })
            else:
                if len(content) > 1000:
                    words = content.split()
                    current_chunk: list[str] = []
                    current_size = 0
                    for word in words:
                        current_chunk.append(word)
                        current_size += len(word) + 1
                        if current_size > 500:
                            chunks.append({"text": " ".join(current_chunk), "metadata": {}})
                            current_chunk = []
                            current_size = 0
                    if current_chunk:
                        chunks.append({"text": " ".join(current_chunk), "metadata": {}})
                else:
                    chunks.append({"text": content, "metadata": {}})
            return chunks

        def _resolve_agent_path(pattern: str) -> Path | None:
            if not pattern.startswith("database/"):
                return None
            current = Path(__file__).resolve()
            candidates = [
                current.parent,
                current.parent.parent,
                current.parent.parent.parent,
            ]
            for parent in candidates:
                if (parent / "pyproject.toml").exists() or (parent / "setup.py").exists():
                    return parent / pattern
            return None

        for index_name, source_patterns in doc_map.items():
            for pattern in source_patterns:
                file_path = repo_path / pattern
                fallback_path = _resolve_agent_path(pattern)
                matches: list[Path] = []
                if file_path.exists():
                    matches.append(file_path)
                else:
                    matches.extend(list(repo_path.glob(pattern)))
                    if fallback_path and fallback_path.exists():
                        matches.append(fallback_path)
                for match in matches:
                    if not match.is_file():
                        continue
                    content = _read_document(match)
                    if not content:
                        continue
                    for chunk in _chunk_document(content):
                        docs.append({
                            "text": chunk["text"],
                            "metadata": {
                                "source": match.name,
                                "index_type": index_name,
                                **chunk.get("metadata", {}),
                            },
                        })
                        if len(docs) >= limit:
                            return docs
        return docs

    def _override_static(
        self,
        user_prompt: str,
        code_name: str,
        baseline_result: dict,
        case_path: str,
        local_path: Path,
        repo_path: Path,
        parameter_resolution_feedback,
    ) -> SimulationPlan:
        """Override with static docs/inputs only (no embeddings)."""
        if code_name not in self.code_configs:
            raise ValueError(f"No config found for override solver {code_name}")

        solver_config = self.code_configs[code_name]

        self._ensure_baseline_inputs_content(
            baseline_result=baseline_result,
            solver_config=solver_config,
            default_local_path=local_path,
            default_repo_path=repo_path,
        )

        # Collect static docs from documentation_map (no embeddings)
        docs = self._collect_static_docs(solver_config, repo_path=repo_path)
        logger.debug(f"[Override] Collected {len(docs)} static docs for {code_name}")

        # Extract modifications from user prompt against baseline
        cbr_plan = self.extract_physics_modifications(
            user_prompt,
            baseline_result["selected_case"]["metadata"].get("inputs_content", {}),
            parameter_resolution_feedback=parameter_resolution_feedback,
            solver_config=solver_config,
        )
        cbr_plan["baseline_case"] = case_path
        cbr_plan["override"] = True

        plan = SimulationPlanFactory.create_from_rag(
            solver_name=code_name,
            baseline_result=baseline_result,
            cbr_plan=cbr_plan,
            docs=docs,
            user_prompt=user_prompt,
            solver_confidence=1.0,
            used_llm=False,
        )
        plan.indexing_strategy = "override_static"
        return plan


    def _override_simple(
        self,
        user_prompt: str,
        code_name: str,
        baseline_result: dict,
        case_path: str,
        local_path: Path,
        repo_path: Path,
        parameter_resolution_feedback
    ) -> SimulationPlan:
        """
        Apply simple strategy with override.

        Flow:
        1. Build requirements with override solver
        2. Gather knowledge
        3. Build baseline dict for simple pipeline
        4. Return plan with 0 modifications
        """
        # Extract requirements (solver forced to override)
        requirements = self._extract_requirements(user_prompt)
        requirements['solver'] = code_name
        requirements['solver_source'] = 'baseline_override'
        solver_config = self.code_configs.get(code_name)

        # Gather knowledge
        knowledge = self._gather_knowledge(user_prompt, requirements)

        # Build baseline dict for simple pipeline
        baseline = {
            'code': code_name,
            'code_name': code_name,
            'path': case_path,
            'case_path': case_path,
            'name': f"{code_name}/{case_path}",
            'local_path': str(local_path),
            'repo_path': str(repo_path),
            'match_score': 1.0,
            'match_rationale': "User-specified baseline override",
            'override': True
        }

        self._ensure_baseline_inputs_content(
            baseline_result=baseline_result,
            solver_config=solver_config,
            default_local_path=local_path,
            default_repo_path=repo_path,
        )

        # Extract modifications from user prompt against baseline
        inputs_content = baseline_result.get('selected_case', {}).get('metadata', {}).get('inputs_content', {})
        llm_result = self.extract_physics_modifications(
            user_prompt,
            inputs_content,
            parameter_resolution_feedback=parameter_resolution_feedback,
            solver_config=solver_config,
        )
        modifications = llm_result.get('modifications', [])

        tier1_overrides = self._extract_tier1_overrides(
            prompt=user_prompt,
            solver_name=code_name,
            solver_config=solver_config,
        )
        if tier1_overrides:
            modifications.extend(tier1_overrides)

        if modifications:
            merged = {}
            for param, value in modifications:
                if param not in merged:
                    merged[param] = value
            modifications = list(merged.items())

        logger.debug(f"[Override] Extracted {len(modifications)} modifications")

        # Plan visualization and analysis (still useful for override)
        visualization = self._plan_visualization(requirements, baseline)
        analysis = self._plan_analysis(requirements)

        # Build plan using factory
        return SimulationPlanFactory.create_from_simple(
            requirements=requirements,
            baseline=baseline,
            modifications=modifications,
            visualization=visualization,
            analysis=analysis,
            user_prompt=user_prompt,
            knowledge=knowledge
        )

    def _calculate_diff(self, base: dict, target: dict) -> list:
        """
        Calculate parameter differences between base and target.

        Args:
            base: Baseline inputs_content dict
            target: Target case inputs_content dict

        Returns
        -------
            List of (param_name, target_value) tuples for changed params

        TODO (Future Enhancement - Parameter Grouping):
            When a parameter like 'amr.max_level' changes, we should also
            consider related parameters in the same "section":

        Examples
        --------
            - amr.max_level → amr.ref_ratio, amr.blocking_factor
            - tagging.* → All tagging parameters as a group
            - chemistry.chem_file → chemistry.do_react, chemistry.use_typ_vals_chem
            # #######################
            # # Domain-specific: combustion chemistry dependencies (handled in database/configs)
            # #######################

            This would ensure parameter consistency. For now, we diff all
            parameters independently, but grouping logic could be added via:

            PARAMETER_GROUPS = {
                'amr': ['max_level', 'ref_ratio', 'blocking_factor', 'max_grid_size'],
                'tagging': ['temperr', 'tempgrad', 'max_temperr_lev', 'ftracerr'],
                'chemistry': ['chem_file', 'do_react', 'use_typ_vals_chem']
            }

            Then when 'amr.max_level' changes, we'd also diff all 'amr.*' params.
        """
        diffs = []

        for key, value in target.items():
            if key in base and base[key] != value:
                # Parameter changed
                diffs.append((key, value))
            elif key not in base:
                # New parameter in target (e.g., adding chemistry)
                diffs.append((key, value))

        return diffs

    def _map_query_to_indices(self, query: str) -> list[str]:
        """
        Map query keywords to relevant Level 2 indices.

        Returns
        -------
            List of index names to target for retrieval.
        """
        query_lower = query.lower()

        grid_keywords = {
            "grid", "resolution", "cell", "n_cell", "mesh", "amr",
            "refine", "refinement", "level", "levels", "block"
        }
        chemistry_keywords = {
            "chem", "chemistry", "mechanism", "react", "reaction",
            "fuel", "oxidizer", "premixed", "flame", "combustion", "dodecane"
        }
        domain_keywords = {
            "combustion", "flame", "turbulence", "detonation"
        }

        indices = []
        if any(word in query_lower for word in grid_keywords):
            indices.append("grid_specifications")
        if any(word in query_lower for word in chemistry_keywords):
            indices.append("chemistry_mechanisms")
        if any(word in query_lower for word in domain_keywords):
            indices.append("domain_models")

        if not indices:
            indices.append(LEVEL2_BASE_KEYS[0])

        # If indices exist on disk, filter to available types but keep a fallback.
        available_types = set()
        try:
            index_dir = self.config.faiss_db_path / "level2"
            for index_file in index_dir.glob("*_case_*.faiss"):
                name = index_file.stem
                if "_case_" in name:
                    available_types.add(name.split("_case_", 1)[1])
        except Exception:
            available_types = set()

        if available_types:
            filtered = [idx for idx in indices if idx in available_types]
            if filtered:
                return filtered

        return indices

    def _llm_plan(
        self,
        prompt: str,
        solver: str,
        documentation: list[dict],
        cases: list[dict],
        previous_errors: list[str] | None = None,
    ) -> LLMPlanResult:
        """Generate a modification plan using an LLM response."""
        llm = getattr(self, "llm", None) or getattr(self, "llm_client", None)
        if not llm:
            return LLMPlanResult(modifications=[], reasoning="LLM unavailable")

        temperature = getattr(self.config, "llm_temperature", 0.1)

        # Minimal prompt assembly; keep outputs JSON-only.
        messages = [
            {
                "role": "system",
                "content": (
                    "Return JSON only with keys: modifications, reasoning. "
                    "Do not include markdown."
                ),
            },
            {"role": "user", "content": prompt},
        ]

        content = ""
        try:
            import instructor
            from pydantic import BaseModel, Field
            from src.config import unwrap_llm_client, wrap_llm_client

            class Modification(BaseModel):
                parameter: str
                value: str

            class LLMPlanResponse(BaseModel):
                modifications: list[Modification]
                reasoning: str = Field(default="")

            base_client = unwrap_llm_client(llm)
            instr_client = instructor.from_openai(base_client)
            instr_client = wrap_llm_client(instr_client, self.config)
            result = instr_client.chat.completions.create(
                model=getattr(self.config, "llm_model", None),
                response_model=LLMPlanResponse,
                messages=messages,
                temperature=temperature,
            )
            raw_mods = [
                {"parameter": mod.parameter, "value": mod.value}
                for mod in result.modifications
            ]
            reasoning = result.reasoning or ""
        except Exception:
            from src.config import unwrap_llm_client, wrap_llm_client

            base_client = unwrap_llm_client(llm)
            client = wrap_llm_client(base_client, self.config)
            try:
                response = client.chat.completions.create(
                    model=getattr(self.config, "llm_model", None),
                    messages=messages,
                    response_format={"type": "json_object"},
                    temperature=temperature,
                )
            except Exception:
                response = client.chat.completions.create(
                    model=getattr(self.config, "llm_model", None),
                    messages=messages,
                    temperature=temperature,
                )
            if hasattr(response, "choices") and response.choices:
                message = getattr(response.choices[0], "message", None)
                content = getattr(message, "content", "") if message else ""
            raw_mods = []
            reasoning = ""

        if not raw_mods:
            # Strip markdown code fences if present.
            cleaned = content.strip()
            if "```" in cleaned:
                fenced_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
                if fenced_match:
                    cleaned = fenced_match.group(1).strip()

            try:
                data = json.loads(cleaned)
            except Exception as exc:
                logger.error("Failed to parse LLM JSON response: %s", exc)
                return LLMPlanResult(
                    modifications=[],
                    reasoning="Failed to parse LLM response",
                )

            raw_mods = data.get("modifications", [])
            reasoning = data.get("reasoning", "")

        # Build allowed parameter set from baseline cases.
        allowed_params = set()
        for case in cases:
            inputs_content = case.get("metadata", {}).get("inputs_content", {})
            allowed_params.update(inputs_content.keys())

        known_auxiliary = set(get_chemistry_param_keys(solver))
        known_auxiliary.update(get_reaction_flag_keys(solver))

        valid_mods = []
        for mod in raw_mods:
            if isinstance(mod, dict):
                param = mod.get("parameter")
                value = mod.get("value")
            elif isinstance(mod, str):
                if "=" in mod:
                    param, value = (part.strip() for part in mod.split("=", 1))
                elif ":" in mod:
                    param, value = (part.strip() for part in mod.split(":", 1))
                else:
                    continue
            else:
                continue
            if not isinstance(param, str) or not isinstance(value, str):
                continue
            if "." not in param:
                continue
            if param not in allowed_params and param not in known_auxiliary:
                continue
            valid_mods.append((param, value))

        if not reasoning:
            reasoning = "LLM plan generated"

        return LLMPlanResult(modifications=valid_mods, reasoning=reasoning)

    def _create_plan_with_override(
        self,
        user_prompt: str,
        baseline_override: str,
        strategy: str,
        **kwargs
    ) -> SimulationPlan:
        """
        Create plan using hardcoded baseline override.

        Skips L2 baseline selection and uses specified case directly.
        Still performs L0 (solver) and L3 (modifications) if using hierarchical.

        Args:
            user_prompt: User's request
            baseline_override: Baseline path (e.g., '<repo_name>/Exec/<problem_directory>')
            strategy: 'simple' or 'hierarchical'
            **kwargs: Additional args

        Returns
        -------
            SimulationPlan with overridden baseline
        """
        # Parse override format: 'Code/Path' or just 'Path'
        if '/' in baseline_override:
            parts = baseline_override.split('/')
            code_registry = self.config.get_code_registry()
            if parts[0] in code_registry:
                code_name = parts[0]
                case_path = '/'.join(parts[1:])
            else:
                raise ValueError(
                    f"Baseline override '{baseline_override}' missing code prefix. "
                    f"Use format: 'SolverName/Path'. Available: {list(code_registry.keys())}"
                )
        else:
            raise ValueError(
                "Baseline override must contain '/'. Format: 'SolverName/Path'"
            )

        logger.debug(f"Override parsed: {code_name}/{case_path}")

        # Build baseline result dict (mimics L2 output)
        repo_path = getattr(self.config, f'{code_name.lower()}_repo_path', None)
        if not repo_path:
            raise ValueError(f"Repository path not configured for {code_name}")

        from pathlib import Path
        local_path = Path(repo_path) / case_path

        baseline_result = {
            'selected_case': {
                'case': case_path,
                'metadata': {
                    'code': code_name,
                    'path': case_path,
                    'name': f"{code_name}/{case_path}",
                    'local_path': str(local_path),
                    'repo_path': str(repo_path)
                }
            },
            'confidence': 1.0,
            'candidates': [],
            'override': True
        }

        if strategy == "hierarchical":
            # Use hierarchical pipeline but skip L2
            try:
                # Still do L0 (solver selection) for validation
                solver_config, solver_confidence = self.select_solver(user_prompt)
                detected_solver = solver_config.code_name if solver_config else code_name

                if detected_solver != code_name:
                    logger.warning(
                        f"L0 detected {detected_solver} but override specifies {code_name}. "
                        f"Using override."
                    )
                    # Override: create config for override solver
                    from database.configs import discover_code_configs
                    configs_list = discover_code_configs()
                    # Convert list to dict: {code_name: config_class}
                    configs = {cfg.code_name: cfg for cfg in configs_list}
                    solver_config = configs.get(code_name)
                    if not solver_config:
                        raise ValueError(f"No config found for override solver {code_name}")
                    logger.debug(f"[Override] Using {code_name} config for context retrieval")

                # Retrieve context (L1) - uses override solver config
                docs = self.retrieve_context(user_prompt, solver_config)
                logger.debug(f"[Override] Retrieved {len(docs)} docs for {code_name}")

                # Skip modifications for baseline override
                # User specified exact baseline - use it as-is
                logger.debug("[Override] Skipping modifications - using baseline as-is")
                cbr_plan = {
                    'modifications': [],  # No modifications
                    'evidence': [],
                    'confidence': 1.0,
                    'baseline_case': case_path,
                    'override': True
                }

                # Build plan using factory
                return SimulationPlanFactory.create_from_rag(
                    solver_name=code_name,
                    baseline_result=baseline_result,
                    cbr_plan=cbr_plan,
                    docs=docs,
                    user_prompt=user_prompt,
                    solver_confidence=1.0,
                    used_llm=False
                )
            except Exception as e:
                logger.warning(f"Hierarchical with override failed: {e}, falling back to simple")
                strategy = "simple"

        # Simple strategy with override
        requirements = self._extract_requirements(user_prompt)
        requirements['solver'] = code_name

        knowledge = self._gather_knowledge(user_prompt, requirements)

        # Build baseline dict for simple pipeline
        baseline = {
            'code': code_name,
            'code_name': code_name,
            'path': case_path,
            'case_path': case_path,
            'name': f"{code_name}/{case_path}",
            'local_path': str(local_path),
            'repo_path': str(repo_path),
            'match_score': 1.0,
            'match_rationale': f"User-specified baseline override: {baseline_override}",
            'override': True
        }

        modifications = self._plan_modifications(requirements, baseline, knowledge)
        visualization = self._plan_visualization(requirements, baseline)
        analysis = self._plan_analysis(requirements)

        return SimulationPlanFactory.create_from_simple(
            requirements=requirements,
            baseline=baseline,
            modifications=modifications,
            visualization=visualization,
            analysis=analysis,
            user_prompt=user_prompt,
            knowledge=knowledge
        )

    def _generate_reasoning_from_plan(self, plan: dict) -> str:
        """Generate reasoning text from simple plan structure."""
        baseline = plan.get('baseline', {})
        requirements = plan.get('requirements', {})

        parts = []
        if baseline.get('name'):
            parts.append(f"Selected baseline: {baseline['name']}")
        if requirements.get('solver'):
            parts.append(f"Using solver: {requirements['solver']}")
        if len(plan.get('modifications', [])) > 0:
            parts.append(f"{len(plan['modifications'])} modifications planned")

        return ". ".join(parts) if parts else "Plan created successfully"

    def create_plan_rag(
        self,
        user_prompt: str,
        excluded_cases: list[str] = None,
        excluded_inputs_files: list[str] = None,
        parameter_resolution_feedback: dict[str, Any] = None,
    ) -> SimulationPlan:
        """
        Architect Service: Orchestration Logic: RAG-based plan creation using Architect Service: Solver Selection / Context Retrieval / Baseline Selection / Modification Planning.

        Call context: Used by the Architect node when hierarchical RAG is enabled.

        Parameters
        ----------
        user_prompt : str
            User's natural language requirement.
        excluded_cases : list of str, optional
            Cases to exclude from selection.
        excluded_inputs_files : list of str, optional
            Input files to exclude from selection.
        parameter_resolution_feedback : dict or None, optional
            Feedback from input_writer for parameter remapping.

        Returns
        -------
        SimulationPlan
            Plan with solver, baseline, modifications, and reasoning.
        """
        # 1. Select Solver (Architect Service: Solver Selection)
        solver_config, solver_confidence = self.select_solver(user_prompt)
        if not solver_config:
            raise ValueError("No suitable solver found")

        solver_name = solver_config.code_name

        # 2. Retrieve Context (Architect Service: Context Retrieval)
        docs = self.retrieve_context(user_prompt, solver_config)

        # 3. Select Baseline (Architect Service: Baseline Selection)
        excluded_cases = excluded_cases or []
        baseline_result = self.select_baseline(
            user_prompt,
            solver_config,
            excluded_cases=excluded_cases
        )

        if not baseline_result:
            if self.config.faiss_fallback_to_llm:
                if hasattr(self, '_llm_plan'):
                    llm_plan = self._llm_plan(
                        prompt=user_prompt,
                        solver=solver_name,
                        documentation=docs,
                        cases=[],
                        previous_errors=None,
                    )
                    baseline_result = {
                        "selected_case": {"case": "unknown", "metadata": {}},
                        "confidence": 0.0,
                        "candidates": [],
                    }
                    cbr_plan = {
                        "modifications": llm_plan.modifications,
                        "reasoning": llm_plan.reasoning,
                        "confidence": 0.5,
                        "similar_cases": [],
                        "used_llm": True,
                    }
                    return SimulationPlanFactory.create_from_rag(
                        solver_name=solver_name,
                        baseline_result=baseline_result,
                        cbr_plan=cbr_plan,
                        docs=docs,
                        user_prompt=user_prompt,
                        solver_confidence=solver_confidence,
                        used_llm=True,
                    )
                else:
                    raise ValueError("No baseline found and LLM not available")
            else:
                raise ValueError("No baseline found and LLM fallback disabled")

        baseline_case = baseline_result['selected_case']
        baseline_conf = baseline_result['confidence']

        self._ensure_baseline_inputs_content(
            baseline_result=baseline_result,
            solver_config=solver_config,
        )

        # 4. Plan Modifications (Architect Service: Modification Planning)
        cbr_plan = self.plan_modifications(
            user_prompt,
            baseline_case,
            solver_code=solver_name,
            parameter_resolution_feedback=parameter_resolution_feedback,  # Pass through
        )
        cbr_conf = cbr_plan.get('confidence', 0.0)

        # 5. Decision Logic (Architect Service: Orchestration Logic)
        use_llm = False

        if baseline_conf > 0.85 and cbr_conf == 1.0:
            use_llm = False
        elif hasattr(self.config, 'faiss_fallback_to_llm') and self.config.faiss_fallback_to_llm:
            use_llm = True
        else:
            use_llm = False

        if use_llm and hasattr(self, '_llm_plan'):
            llm_plan = self._llm_plan(
                prompt=user_prompt,
                solver=solver_name,
                documentation=docs,
                cases=[baseline_case],
                previous_errors=None
            )
            cbr_plan = {
                "modifications": llm_plan.modifications,
                "reasoning": llm_plan.reasoning,
                "confidence": 0.5,
                "similar_cases": [
                    baseline_case.get("case")
                    or baseline_case.get("metadata", {}).get("repo_path")
                    or "baseline"
                ],
                "used_llm": True,
            }
            return SimulationPlanFactory.create_from_rag(
                solver_name=solver_name,
                baseline_result=baseline_result,
                cbr_plan=cbr_plan,
                docs=docs,
                user_prompt=user_prompt,
                solver_confidence=solver_confidence,
                used_llm=True,
            )

        return SimulationPlanFactory.create_from_rag(
            solver_name=solver_name,
            baseline_result=baseline_result,
            cbr_plan=cbr_plan,
            docs=docs,
            user_prompt=user_prompt,
            solver_confidence=solver_confidence,
            used_llm=False
        )

    def create_plan(
        self,
        user_prompt: str,
        prefer_quality: str = "good",
        weights: dict[str, float] | None = None,
        previous_feedback: dict[str, Any] | None = None,
        knowledge_limit: int = 3,
        excluded_cases: list = None,
        excluded_inputs_files: list = None,
        parameter_resolution_feedback: dict[str, Any] | None = None
    ) -> SimulationPlan:
        """
        Create complete simulation plan from prompt.

        Call context: Used by the Architect node for non-RAG planning.

        Parameters
        ----------
        user_prompt : str
            Natural language simulation request.
        prefer_quality : str, optional
            Quality preference for baseline selection.
        weights : dict or None, optional
            Custom weights for 5-bucket scoring.
        previous_feedback : dict or None, optional
            Feedback from previous iterations.
        knowledge_limit : int, optional
            Max knowledge items to include.
        excluded_cases : list or None, optional
            Baseline cases to exclude.
        excluded_inputs_files : list or None, optional
            Input files to exclude.
        parameter_resolution_feedback : dict or None, optional
            Feedback from input_writer for parameter remapping.

        Returns
        -------
        SimulationPlan
            Structured plan for the simulation.
        """
        logger.debug("\n=== Creating Simulation Plan ===\n")
        logger.debug(f"Prompt: {user_prompt}\n")

        # Extract structured requirements from prompt
        requirements = self._extract_requirements(user_prompt)
        logger.debug(f"Requirements: {requirements}\n")

        # Gather domain knowledge from KB
        knowledge = self._gather_knowledge(user_prompt, requirements)
        logger.debug(f"Knowledge gathered: {list(knowledge.keys())}\n")

        # Select baseline case using 5-bucket scoring
        baseline = self._select_baseline(
            requirements=requirements,
            user_prompt=user_prompt,
            prefer_quality=prefer_quality,
            weights=weights
        )

        if not baseline:
            raise ValueError("No suitable baseline case found")

        logger.debug(f"Selected baseline: {baseline.get('name', 'unknown')}\n")

        # Plan parameter modifications
        modifications = self._plan_modifications(
            requirements=requirements,
            baseline=baseline,
            knowledge=knowledge
        )

        # Apply parameter remapping feedback from reviewer/input-writer if provided
        if parameter_resolution_feedback:
            suggested = parameter_resolution_feedback.get("suggested_params", {})
            remap_mapping = parameter_resolution_feedback.get("remap_mapping", {})
            if suggested:
                remapped = []
                for param, value in modifications:
                    target = remap_mapping.get(param)
                    if target is None:
                        target = suggested.get(param, param)
                        if isinstance(target, list):
                            target = target[0] if target else param
                    remapped.append((target, value))
                modifications = remapped
                if previous_feedback:
                    previous_feedback = {
                        **previous_feedback,
                        "suggested_params": suggested,
                    }
                else:
                    previous_feedback = {"suggested_params": suggested}
            unresolved = parameter_resolution_feedback.get("unresolved_parameters", [])
            if unresolved:
                unresolved_errors = []
                for entry in unresolved:
                    param = entry
                    if isinstance(entry, (list, tuple)) and entry:
                        param = entry[0]
                    if not param:
                        continue
                    unresolved_errors.append(f"{param} not specified")
                if unresolved_errors:
                    if previous_feedback:
                        prior_errors = previous_feedback.get("errors", [])
                        previous_feedback = {
                            **previous_feedback,
                            "errors": prior_errors + unresolved_errors,
                        }
                    else:
                        previous_feedback = {"errors": unresolved_errors}

        # Apply feedback if provided
        if previous_feedback:
            fixes = self._parse_errors_into_fixes(
                previous_feedback.get('errors', []),
                user_prompt
            )
            modifications.extend(fixes)

        # Plan visualization
        visualization = self._plan_visualization(requirements, baseline)

        # Plan analysis
        analysis = self._plan_analysis(requirements)

        # Use factory to create plan from simple pipeline outputs
        plan = SimulationPlanFactory.create_from_simple(
            requirements=requirements,
            baseline=baseline,
            modifications=modifications,
            visualization=visualization,
            analysis=analysis,
            user_prompt=user_prompt,
            knowledge=knowledge
        )

        logger.debug(f"\n[PASS] Plan created with {len(plan.modifications)} modifications")
        # logger.debug(f"\n[PASS] Plan created with {len(modifications)} modifications, {len(visualization['plots'])} plots, {len(analysis['checks'])} checks")
        logger.debug(f"       Overall confidence: {plan.get_overall_confidence():.2%}\n")

        return plan

    def extract_physics_modifications(
            self,
            case_description: str,
            inputs_content: str | dict,
            parameter_resolution_feedback: dict[str, Any] = None,
            solver_config=None,
            client=None
    ) -> dict:
        """
        Extract parameter modifications from a physics description using an LLM.

        Call context: Used by Architect planning when retrieval is sparse.

        Parameters
        ----------
        case_description : str
            Natural language description of the simulation case.
        inputs_content : str or dict
            Baseline input content.
        parameter_resolution_feedback : dict or None, optional
            Feedback containing unresolved parameters and suggestions.
        solver_config : object, optional
            Solver config for prompt templates.
        client : object, optional
            Optional pre-configured OpenAI client.

        Returns
        -------
        dict
            Payload with modifications, confidence, and used_llm flags.
        """
        if isinstance(inputs_content, dict):
            inputs_content = "\n".join(f"{k} = {v}" for k, v in inputs_content.items())

        logger.debug(f"[LLM] extract_physics_modifications called with feedback: {parameter_resolution_feedback is not None}")
        if parameter_resolution_feedback:
            logger.debug(f"[LLM] Feedback contains: {list(parameter_resolution_feedback.keys())}")

        # If we have explicit remap guidance, apply it directly (skip LLM)
        if parameter_resolution_feedback:
            remap_mapping = parameter_resolution_feedback.get("remap_mapping", {})
            unresolved = parameter_resolution_feedback.get("unresolved_parameters", [])
            if remap_mapping and unresolved:
                remapped = []
                for param, value in unresolved:
                    target = remap_mapping.get(param, param)
                    remapped.append((target, value))
                logger.debug(f"[LLM] Using remap_mapping for {len(remapped)} parameters")
                return {
                    "modifications": remapped,
                    "confidence": 1.0,
                    "used_llm": False
                }

        available_params = []
        schema_scan_notes = ""
        if not parameter_resolution_feedback and solver_config:
            available_params = self._load_schema_params(solver_config)
            baseline_params = self._collect_baseline_params(inputs_content)
            scan_result = self._call_llm_for_schema_scan(
                case_description=case_description,
                baseline_params=baseline_params,
                available_params=available_params,
                solver_config=solver_config,
                client=client,
            )
            unresolved_concepts = scan_result.get("unresolved_concepts", [])
            if unresolved_concepts:
                schema_scan_notes = (
                    "\nSCHEMA SCAN NOTES:\n"
                    "The following concepts did NOT map to baseline or schema parameters:\n"
                    + "\n".join(f"- {concept}" for concept in unresolved_concepts)
                    + "\nIf any have an exact parameter mapping, include it; otherwise skip."
                )

        def _build_tier_guidance(tier_name: str, params: list[str], notes: str) -> str:
            if not params:
                return notes
            param_list = ", ".join(params)
            notes_section = f"{notes}\n" if notes else ""
            return (
                f"{notes_section}PRIORITY PARAMETERS ({tier_name}):\n"
                f"  {param_list}\n\n"
                "MATCHING INSTRUCTIONS:\n"
                "1. Prefer exact parameter names from this list when they apply.\n"
                "2. If the needed parameter is not in this list, use the exact name from the baseline input file.\n"
                "3. If no exact match exists in either place, SKIP that modification.\n"
                "CRITICAL: Parameter names are case-sensitive and must include the full prefix."
            )

        def _merge_with_overrides(
            base_mods: list[tuple[str, str]],
            extra_mods: list[tuple[str, str]],
            override_params: set[str],
        ) -> list[tuple[str, str]]:
            merged = {}
            for param, value in base_mods:
                if param not in merged:
                    merged[param] = value
            for param, value in extra_mods:
                if param in merged and param not in override_params:
                    continue
                merged[param] = value
            return list(merged.items())

        def _run_guidance_pass(
            pass_name: str,
            chunks: list[str],
        ) -> dict:
            chunk_results: list[list[tuple[str, str]]] = []
            chunk_errors: list[str] = []
            for chunk_idx, param_guidance in enumerate(chunks):
                logger.debug(f"[LLM] {pass_name} pass chunk {chunk_idx+1}/{len(chunks)}")
                result = self._call_llm_for_modifications(
                    case_description=case_description,
                    inputs_content=inputs_content,
                    param_guidance=param_guidance,
                    solver_config=solver_config,
                    client=client,
                )
                if result.get('success'):
                    chunk_results.append(result['modifications'])
                else:
                    chunk_errors.append(result.get('error'))
                    logger.warning(
                        f"[LLM] {pass_name} chunk {chunk_idx+1} failed: {result.get('error')}"
                    )

            modifications: list[tuple[str, str]] = []
            merge_warnings: list[str] = []
            if chunk_results:
                modifications, merge_warnings = self._merge_modifications(
                    chunk_results,
                    case_description,
                )

            return {
                "pass_name": pass_name,
                "modifications": modifications,
                "merge_warnings": merge_warnings,
                "errors": chunk_errors,
                "chunks_total": len(chunks),
                "chunks_processed": len(chunk_results),
            }

        def _merge_passes(
            base_pass: dict,
            extra_pass: dict,
            override_params: set[str],
        ) -> dict:
            merged_mods = _merge_with_overrides(
                base_pass.get("modifications", []),
                extra_pass.get("modifications", []),
                override_params,
            )
            merge_warnings = (base_pass.get("merge_warnings") or []) + (
                extra_pass.get("merge_warnings") or []
            )
            errors = (base_pass.get("errors") or []) + (extra_pass.get("errors") or [])
            return {
                "modifications": merged_mods,
                "merge_warnings": merge_warnings,
                "errors": errors,
            }

        def _needs_schema_fallback(
            merged_mods: list[tuple[str, str]],
            prompt_text: str,
            tier1_params: list[str],
            tier2_params: list[str],
        ) -> bool:
            if not merged_mods:
                return True
            mods_set = {param for param, _ in merged_mods}
            if tier1_params or tier2_params:
                tier_params = set(tier1_params) | set(tier2_params)
                if tier_params and not mods_set.intersection(tier_params):
                    return True
            if len(prompt_text.split()) > 50 and len(merged_mods) < 3:
                return True
            return False

        # Build parameter guidance chunks with tiered fallback for context limits
        param_chunks = []
        fallback_level = 0  # 0=category chunks, 1=suggested only, 2=fixed-size chunks
        failed_section = ""
        tier1_params = []
        tier2_params = []

        if parameter_resolution_feedback:
            unresolved = parameter_resolution_feedback.get('unresolved_parameters', [])
            suggested = parameter_resolution_feedback.get('suggested_params', {})
            available = parameter_resolution_feedback.get('available_schema_params', [])

            logger.debug(
                f"[LLM] Parameter resolution feedback: "
                f"{len(unresolved)} failed, {len(available)} valid params available"
            )

            # Build failed params section (always include)
            failed_lines = []
            for param_name, attempted_value in unresolved:
                suggestions = suggested.get(param_name, [])[:5]
                if suggestions:
                    failed_lines.append(
                        f"  - \"{param_name}\" (value: {attempted_value}) → "
                        f"try instead: {', '.join(suggestions)}"
                    )
                else:
                    failed_lines.append(
                        f"  - \"{param_name}\" (value: {attempted_value}) → no suggestions"
                    )

            failed_section = f"""
PARAMETER RESOLUTION FEEDBACK:
The following parameters were NOT recognized in a previous attempt:
{chr(10).join(failed_lines)}
"""
            if schema_scan_notes:
                failed_section = f"{schema_scan_notes}\n{failed_section}"
            # Collect all suggested params for fallback
            all_suggested = set()
            for suggestions in suggested.values():
                all_suggested.update(suggestions[:10])

            param_chunks = self._build_param_guidance(
                failed_section=failed_section,
                available=available,
                all_suggested=list(all_suggested),
                fallback_level=fallback_level,
                solver_config=solver_config,
            )
        else:
            tier1_params, tier2_params = self._get_tier_params(
                solver_config, available_params
            ) if solver_config else ([], [])
            # No feedback: multi-pass (baseline-only, then tier-priority, then schema fallback).
            baseline_pass = _run_guidance_pass("baseline", [schema_scan_notes or ""])

            tier_mods: list[tuple[str, str]] = []
            tier_warnings: list[str] = []
            if tier1_params:
                tier1_guidance = _build_tier_guidance("Tier 1", tier1_params, "")
                tier1_pass = _run_guidance_pass("tier1", [tier1_guidance])
                tier_mods = tier1_pass.get("modifications", [])
                tier_warnings = tier1_pass.get("merge_warnings", [])
                if tier2_params:
                    tier2_guidance = _build_tier_guidance("Tier 2", tier2_params, "")
                    tier2_pass = _run_guidance_pass("tier2", [tier2_guidance])
                    tier2_mods = tier2_pass.get("modifications", [])
                    tier2_warnings = tier2_pass.get("merge_warnings", [])
                    if tier2_mods:
                        tier_mods, tier_warnings = self._merge_modifications(
                            [tier_mods, tier2_mods],
                            case_description,
                        )
                    else:
                        tier_warnings = (tier_warnings or []) + (tier2_warnings or [])

            merged_pass = _merge_passes(
                baseline_pass,
                {"modifications": tier_mods, "merge_warnings": tier_warnings},
                override_params=set(tier1_params) | set(tier2_params),
            )
            merged_mods = merged_pass.get("modifications", [])

            used_schema_fallback = False
            if _needs_schema_fallback(
                merged_mods,
                case_description,
                tier1_params,
                tier2_params,
            ) and available_params:
                used_schema_fallback = True
                param_chunks = self._build_param_guidance(
                    failed_section=schema_scan_notes,
                    available=available_params,
                    all_suggested=[],
                    fallback_level=0,
                    solver_config=solver_config,
                )
                schema_pass = _run_guidance_pass("schema", param_chunks)
                if schema_pass.get("modifications"):
                    merged_pass = _merge_passes(
                        {"modifications": merged_mods, "merge_warnings": tier_warnings},
                        schema_pass,
                        override_params=set(),
                    )
                    merged_mods = merged_pass.get("modifications", [])
                    tier_warnings = merged_pass.get("merge_warnings", [])
                else:
                    tier_warnings.extend(schema_pass.get("merge_warnings") or [])

            confidence = 0.75 if merged_mods else 0.3
            if used_schema_fallback:
                confidence *= 0.9

            return {
                "modifications": merged_mods,
                "confidence": confidence,
                "used_llm": True,
                "parameter_resolution_applied": False,
                "fallback_level": None,
                "chunks_processed": None,
                "chunks_total": None,
                "merge_warnings": (baseline_pass.get("merge_warnings") or []) + (tier_warnings or []),
            }

        # Try with progressively different chunking strategies on failure
        max_fallback = 3 if parameter_resolution_feedback else 1
        last_error = None

        for attempt in range(max_fallback):
            if attempt > 0 and parameter_resolution_feedback:
                # Rebuild chunks with higher fallback level
                fallback_level = attempt
                available = parameter_resolution_feedback.get('available_schema_params', [])
                suggested = parameter_resolution_feedback.get('suggested_params', {})
                all_suggested = set()
                for suggestions in suggested.values():
                    all_suggested.update(suggestions[:10])

                param_chunks = self._build_param_guidance(
                    failed_section=failed_section,
                    available=available,
                    all_suggested=list(all_suggested),
                    fallback_level=fallback_level,
                    solver_config=solver_config,
                )
                logger.debug(f"[LLM] Retrying with fallback level {fallback_level}, {len(param_chunks)} chunks")

            # Process each chunk separately
            chunk_results = []
            chunk_errors = []

            for chunk_idx, param_guidance in enumerate(param_chunks):
                logger.debug(f"[LLM] Processing chunk {chunk_idx+1}/{len(param_chunks)}")

                result = self._call_llm_for_modifications(
                    case_description=case_description,
                    inputs_content=inputs_content,
                    param_guidance=param_guidance,
                    solver_config=solver_config,
                    client=client
                )

                if result.get('success'):
                    chunk_results.append(result['modifications'])
                else:
                    chunk_errors.append(result.get('error'))
                    logger.warning(f"[LLM] Chunk {chunk_idx+1} failed: {result.get('error')}")

            # Check if we got any successful chunks
            if chunk_results:
                # Merge modifications from all chunks
                modifications, merge_warnings = self._merge_modifications(
                    chunk_results,
                    case_description
                )

                # Adjust confidence based on success rate and retry state
                success_rate = len(chunk_results) / len(param_chunks)

                if parameter_resolution_feedback:
                    base_confidence = 0.6 if modifications else 0.2
                else:
                    base_confidence = 0.75 if modifications else 0.3

                # Reduce confidence if some chunks failed
                confidence = base_confidence * success_rate

                # Lower confidence further if we had to fall back
                if fallback_level > 0:
                    confidence *= 0.9

                # If a tier1 parameter was modified, request a tier2 pass for related params.
                if not parameter_resolution_feedback and tier1_params and tier2_params:
                    modified_params = {param for param, _ in modifications}
                    if modified_params.intersection(tier1_params):
                        tier2_guidance = _build_tier_guidance("Tier 2", tier2_params, "")
                        tier2_result = self._call_llm_for_modifications(
                            case_description=case_description,
                            inputs_content=inputs_content,
                            param_guidance=tier2_guidance,
                            solver_config=solver_config,
                            client=client
                        )
                        if tier2_result.get('success') and tier2_result.get('modifications'):
                            modifications, merge_warnings = self._merge_modifications(
                                [modifications, tier2_result['modifications']],
                                case_description
                            )

                return {
                    "modifications": modifications,
                    "confidence": confidence,
                    "used_llm": True,
                    "parameter_resolution_applied": parameter_resolution_feedback is not None,
                    "fallback_level": fallback_level,
                    "chunks_processed": len(chunk_results),
                    "chunks_total": len(param_chunks),
                    "merge_warnings": merge_warnings
                }

            # All chunks failed for this attempt
            last_error = chunk_errors[0] if chunk_errors else "Unknown error"

            # Check if error is context-related (worth retrying with different chunking)
            error_str = str(last_error).lower()
            if 'context' in error_str or 'token' in error_str or 'length' in error_str:
                logger.warning("[LLM] Context limit hit, trying different chunking strategy")
                continue
            else:
                # Non-context error, don't retry
                break

        # All attempts failed
        logger.warning(f"[LLM] Physics extraction failed after {max_fallback} attempts: {last_error}")
        return {"modifications": [], "confidence": 0.0, "used_llm": True}

    def _merge_modifications(
        self,
        chunk_results: list[list[tuple[str, str]]],
        case_description: str
    ) -> tuple[list[tuple[str, str]], list[str]]:
        """Merge modifications from multiple parameter chunks.

        Args:
            chunk_results: List of modification lists, one per chunk
                          [[('prob.P_mean', '101325'), ...], [('geometry.prob_lo', '0.0'), ...], ...]
            case_description: Original case description (for logging context)

        Returns
        -------
            (merged_modifications, warnings)
            - merged_modifications: Deduplicated list of (parameter, value) tuples
            - warnings: List of issues encountered during merge
        """
        from collections import OrderedDict

        warnings = []
        seen = OrderedDict()  # Preserves insertion order

        for chunk_idx, modifications in enumerate(chunk_results):
            logger.debug(f"[LLM] Merging chunk {chunk_idx+1}/{len(chunk_results)}: {len(modifications)} modifications")

            for param, value in modifications:
                if param in seen:
                    # Parameter found in multiple chunks
                    existing_value = seen[param]
                    if existing_value != value:
                        # Conflict: same parameter, different values
                        warning = (
                            f"Parameter '{param}' found in multiple chunks with different values: "
                            f"'{existing_value}' vs '{value}'. Keeping first occurrence."
                        )
                        warnings.append(warning)
                        logger.warning(f"[LLM] {warning}")
                    else:
                        # Same parameter, same value (duplicate) - just skip
                        logger.debug(f"[LLM] Duplicate '{param}'='{value}' in chunk {chunk_idx+1}, skipping")
                else:
                    # New parameter
                    seen[param] = value

        merged = list(seen.items())

        logger.debug(
            f"[LLM] Merged {sum(len(c) for c in chunk_results)} total modifications "
            f"from {len(chunk_results)} chunks into {len(merged)} unique parameters"
        )

        if warnings:
            logger.warning(f"[LLM] Merge produced {len(warnings)} warnings")

        return merged, warnings

    def _build_param_guidance(
            self,
            failed_section: str,
            available: list[str],
            all_suggested: list[str],
            fallback_level: int,
            solver_config=None,
    ) -> list[str]:
        """Build parameter guidance chunks with tiered detail levels.

        Fallback levels:
            0: Category-based chunks (prob, geometry, amr, etc.) - one chunk per category
            1: Suggested params only (single chunk)
            2: Fixed-size chunks of 50 params from available list

        Returns
        -------
            List of guidance strings, one per chunk to be processed separately
        """
        if fallback_level == 0:
            # Category-based chunking
            params_to_show = available
            grouped = self._group_parameters_by_category(
                params_to_show,
                solver_config=solver_config,
            )

            chunks = []
            for category, params in grouped.items():
                param_list = f"  {category}:\n    {', '.join(params)}"

                chunk = f"""{failed_section}

Valid parameters for category '{category}' ({len(params)} parameters):

{param_list}

MATCHING INSTRUCTIONS:
1. Look for physics quantities that belong to the '{category}' category
2. Find exact parameter names from the list above
3. If no exact match exists, SKIP that modification

CRITICAL: Parameter names are case-sensitive and must include the full prefix.
Examples for this category:
  [OK] "{params[0] if params else 'example'}"
  [BAD] Wrong case, missing prefix, or invented names"""

                chunks.append(chunk)

            logger.debug(f"[LLM] Created {len(chunks)} category-based chunks: {list(grouped.keys())}")
            return chunks

        elif fallback_level == 1:
            # Suggested params only - single chunk
            params_to_show = all_suggested if all_suggested else available[:50]
            grouped = self._group_parameters_by_category(
                params_to_show,
                solver_config=solver_config,
            )

            param_list = "\n".join([
                f"  {category}:\n    {', '.join(params)}"
                for category, params in grouped.items()
            ])

            chunk = f"""{failed_section}

Valid parameters (showing {len(params_to_show)} suggested):

{param_list}

MATCHING INSTRUCTIONS:
1. These are the most likely parameters based on previous failures
2. Find exact parameter names from the list above
3. If no exact match exists, SKIP that modification

CRITICAL: Use exact names only."""

            logger.debug(f"[LLM] Created 1 suggested-params chunk with {len(params_to_show)} params")
            return [chunk]

        else:
            # Fixed-size chunking (50 params per chunk)
            params_to_show = all_suggested if all_suggested else available[:200]
            chunk_size = 50

            chunks = []
            for i in range(0, len(params_to_show), chunk_size):
                chunk_params = params_to_show[i:i+chunk_size]
                grouped = self._group_parameters_by_category(
                    chunk_params,
                    solver_config=solver_config,
                )

                param_list = "\n".join([
                    f"  {category}:\n    {', '.join(params)}"
                    for category, params in grouped.items()
                ])

                chunk = f"""{failed_section}

Valid parameters (chunk {i//chunk_size + 1}, showing {len(chunk_params)} parameters):

{param_list}

MATCHING INSTRUCTIONS:
1. Find exact parameter names from THIS chunk only
2. If no exact match exists in this chunk, SKIP (it may be in another chunk)

CRITICAL: Use exact names only."""

                chunks.append(chunk)

            logger.debug(f"[LLM] Created {len(chunks)} fixed-size chunks of {chunk_size} params each")
            return chunks

    def _call_llm_for_modifications(
            self,
            case_description: str,
            inputs_content: str,
            param_guidance: str,
            solver_config=None,
            client=None
    ) -> dict:
        """Call LLM to extract modifications. Returns dict with 'success', 'modifications' or 'error'."""
        from src.utils.gate import _redactor

        def _normalize_llm_value(value: str) -> str:
            if not isinstance(value, str):
                return value
            trimmed = value.strip()
            if trimmed.startswith("[") and trimmed.endswith("]"):
                inner = trimmed[1:-1].strip()
                if inner:
                    return " ".join(part.strip() for part in inner.split(","))
                return ""
            if "," in trimmed and all(part.strip().replace("-", "").replace(".", "").isdigit() for part in trimmed.split(",")):
                return " ".join(part.strip() for part in trimmed.split(","))
            return value

        prompt_template = self._resolve_llm_prompt_template(
            solver_config,
            "modification_extraction",
        )
        prompt = prompt_template.format(
            case_description=case_description,
            inputs_content=inputs_content[:6000],
            param_guidance=param_guidance
        )

        try:
            import instructor
            from src.config import get_llm_client, unwrap_llm_client, wrap_llm_client
            from pydantic import BaseModel, Field

            class Modification(BaseModel):
                parameter: str
                value: str

            class ModificationExtraction(BaseModel):
                working: str = Field(description="Step-by-step reasoning showing parameter mapping and unit conversions")
                modifications: list[Modification]
            if client is None:
                base_client = unwrap_llm_client(get_llm_client(self.config))
                client = instructor.from_openai(base_client)
                client = wrap_llm_client(client, self.config)
            result = client.chat.completions.create(
                model=self.config.llm_model,
                response_model=ModificationExtraction,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            modifications = [(m.parameter, _normalize_llm_value(m.value)) for m in result.modifications]

            # Log reasoning for debugging
            logger.debug(f"[LLM] Working: {result.working}")
            logger.debug(f"[LLM] Extracted {len(modifications)} modifications")
            if not modifications:
                redactor = _redactor()
                raw = result.model_dump_json() if hasattr(result, "model_dump_json") else str(result)
                logger.debug("[LLM] Empty modifications (raw response): %s", redactor(raw))

            return {"success": True, "modifications": modifications}

        except (ModuleNotFoundError, ImportError):
            try:
                import json
                from src.config import get_llm_client
                client = get_llm_client(self.config)
                response = client.chat.completions.create(
                    model=self.config.llm_model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                raw_content = response.choices[0].message.content
                result = json.loads(raw_content)
                modifications = [
                    (m['parameter'], _normalize_llm_value(m.get('value', '')))
                    for m in result.get('modifications', [])
                ]

                # Log reasoning from fallback mode too
                logger.debug(f"[LLM] Working: {result.get('working', 'N/A')}")
                logger.debug(f"[LLM] Extracted {len(modifications)} modifications")
                if not modifications:
                    redactor = _redactor()
                    logger.debug("[LLM] Empty modifications (raw response): %s", redactor(raw_content))

                return {"success": True, "modifications": modifications}
            except Exception as e:
                return {"success": False, "error": e}

        except Exception as e:
            return {"success": False, "error": e}

    def _call_llm_for_schema_scan(
            self,
            case_description: str,
            baseline_params: list[str],
            available_params: list[str],
            solver_config=None,
            client=None
    ) -> dict:
        """Call LLM to surface concepts without schema/baseline matches."""
        prompt_template = self._resolve_llm_prompt_template(
            solver_config,
            "schema_scan",
        )
        max_params = 200
        truncated = available_params[:max_params]
        prompt = prompt_template.format(
            case_description=case_description,
            baseline_params="\n".join(baseline_params[:max_params]),
            schema_param_count=len(available_params),
            schema_params="\n".join(truncated),
        )

        try:
            import instructor
            from src.config import get_llm_client, unwrap_llm_client, wrap_llm_client
            from pydantic import BaseModel, Field

            class SchemaScanResult(BaseModel):
                unresolved_concepts: list[str] = Field(default_factory=list)
                notes: str = ""

            if client is None:
                base_client = unwrap_llm_client(get_llm_client(self.config))
                client = instructor.from_openai(base_client)
                client = wrap_llm_client(client, self.config)
            result = client.chat.completions.create(
                model=self.config.llm_model,
                response_model=SchemaScanResult,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )

            return {
                "unresolved_concepts": result.unresolved_concepts,
                "notes": result.notes,
            }

        except Exception as e:
            logger.debug(f"[LLM] Schema scan failed: {e}")
            return {"unresolved_concepts": [], "notes": ""}

    def _group_parameters_by_category(
        self,
        params: list[str],
        solver_config=None,
    ) -> dict:
        """Group parameters by prefix for easier scanning.

        Parameters
        ----------
        params : list of str
            Parameter names like ["prob.jet_velocity", "geometry.prob_lo", ...].
        solver_config : object or None, optional
            Solver config for category ordering.

        Returns
        -------
        dict
            Mapping category to sorted list of params.
        """
        from collections import defaultdict
        grouped = defaultdict(list)

        for param in params:
            prefix = param.split('.')[0] if '.' in param else 'other'
            grouped[prefix].append(param)

        # Sort categories by common importance for this domain
        from database.configs import BaseAMReXConfig
        category_order = list(
            getattr(
                solver_config,
                "parameter_section_order",
                BaseAMReXConfig.parameter_section_order,
            )
        )

        result = {}
        for cat in category_order:
            if cat in grouped:
                result[cat] = sorted(grouped[cat])

        # Add any remaining categories not in the priority list
        for cat in sorted(grouped.keys()):
            if cat not in result:
                result[cat] = sorted(grouped[cat])

        return result

    def _load_schema_params(self, solver_config) -> list[str]:
        try:
            from pathlib import Path
            from src.services.config_model_factory import ConfigModelFactory
            code_name = getattr(solver_config, "code_name", "")
            repo_root = ""
            if hasattr(self.config, "repositories"):
                repo_root = self.config.repositories.get(code_name, "")
            schema_dir = self.config.amrex_agent_root / "database/schemas"
            schema_path = ConfigModelFactory.resolve_schema_path(
                solver_config,
                schema_dir,
                Path(repo_root or "."),
            )
            schema = ConfigModelFactory.load_schema(schema_path)
            if isinstance(schema, dict) and "parameters" in schema:
                schema = schema["parameters"]
            if isinstance(schema, dict):
                return sorted(schema.keys())
        except Exception as exc:
            logger.debug(f"[LLM] Failed to load schema params: {exc}")
        return []

    def _collect_baseline_params(self, inputs_content: str | dict) -> list[str]:
        if isinstance(inputs_content, str):
            params = []
            for line in inputs_content.splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    params.append(line.split("=", 1)[0].strip())
            return sorted(set(params))
        if isinstance(inputs_content, dict):
            params = set()
            for key, value in inputs_content.items():
                if isinstance(value, dict):
                    for subkey in value.keys():
                        params.add(f"{key}.{subkey}")
                else:
                    params.add(key)
            return sorted(params)
        return []

    def _extract_requirements(self, prompt: str) -> dict[str, Any]:
        """Extract simulation requirements from natural language prompt.

        Enhanced: Uses knowledge base to validate/expand extracted parameters.
        """
        requirements = {}
        prompt_lower = prompt.lower()

        # === EXISTING EXTRACTION (keep as-is) ===
        # Grid
        grid_match = re.search(r'(\d+)\s*[x×]\s*(\d+)(?:\s*[x×]\s*(\d+))?', prompt)
        if grid_match:
            requirements['grid'] = [int(grid_match.group(1)), int(grid_match.group(2))]
            if grid_match.group(3):
                requirements['grid'].append(int(grid_match.group(3)))

        # Fuel
        fuels = ['hydrogen', 'methane', 'propane', 'dodecane', 'ethylene']
        for fuel in fuels:
            if fuel in prompt_lower:
                requirements['fuel'] = fuel
                break

        # Physics
        if any(word in prompt_lower for word in ['flame', 'combustion', 'burn']):
            requirements['physics'] = 'combustion'

        requirements['problem_type'] = self._infer_problem_type(prompt, requirements)

        # === NEW: KNOWLEDGE-ENHANCED VALIDATION ===

        # 1a. Try to parse solver explicitly from prompt FIRST
        if 'solver' not in requirements:
            prompt_lower = prompt.lower()

            # Get available codes from AMReXCases
            available_codes = self.cases.get_code_names()

            # Check for explicit mentions (case-insensitive)
            for code_name in available_codes:
                code_lower = code_name.lower()
                if (code_lower in prompt_lower or
                    f"with {code_lower}" in prompt_lower or
                    f"using {code_lower}" in prompt_lower):
                    requirements['solver'] = code_name
                    requirements['solver_source'] = 'explicit_mention'
                    logger.debug(f"      Detected solver from prompt: {code_name}")
                    break

        # 1b. If still not found, infer from KB
        if 'solver' not in requirements:
            if self.level0_searcher:
                try:
                    selection = self.select_solver(prompt)
                    if selection and selection.code_name:
                        requirements['solver'] = selection.code_name
                        requirements['solver_source'] = 'level0_faiss'
                        requirements['solver_confidence'] = selection.confidence
                        logger.debug(f"      Detected solver from level0: {selection.code_name}")
                except Exception as exc:
                    logger.debug("      Level0 solver selection failed: %s", exc)
            if 'solver' not in requirements:
                solver_question = self._build_solver_selection_question(prompt)
                solver_answer = self.knowledge.query(solver_question)
                requirements['solver'] = self._parse_solver_from_answer(solver_answer['answer'])
                requirements['solver_rationale'] = solver_answer['answer'][:200]
                requirements['solver_source'] = 'knowledge_base'

        # 2. Get recommended CFL for the detected fuel/physics
        if requirements.get('fuel'):
            cfl_question = f"What CFL number is recommended for {requirements['fuel']} combustion simulations?"
            cfl_answer = self.knowledge.query(cfl_question, context=requirements)
            requirements['recommended_cfl'] = self._parse_cfl_from_answer(cfl_answer['answer'])

        # 3. Get chemistry mechanism recommendation
        if requirements.get('fuel'):
            chem_question = f"What chemistry mechanism should I use for {requirements['fuel']}?"
            chem_answer = self.knowledge.query(chem_question, context=requirements)
            requirements['chemistry_mechanism'] = chem_answer['answer'][:300]

        # 4. Validate grid resolution against Kolmogorov scale / flame thickness
        if requirements.get('grid'):
            grid_question = f"Is a base grid of {requirements['grid']} adequate for {requirements.get('physics', 'combustion')}?"
            grid_answer = self.knowledge.query(grid_question, context=requirements)
            requirements['grid_validation'] = grid_answer['answer'][:200]

        requirements['user_prompt'] = prompt
        return requirements

    def _build_solver_selection_question(self, prompt: str) -> str:
        """Generate a targeted question for solver selection.

        Uses cases service to get accurate solver descriptions.
        """
        # Get solver descriptions from cases service
        solver_descriptions = self.cases.get_solver_descriptions()

        # Build options list
        options = [f"- {name}: {desc}"
                   for name, desc in solver_descriptions.items()]
        options_str = '\n'.join(options)

        return f"""Based on this simulation description:

"{prompt}"

Which solver should I use from these options?

{options_str}

Answer with the solver name and brief justification."""

    def _parse_errors_into_fixes(self,
                                 errors: list[str],
                                 user_prompt: str) -> list[tuple[str, Any]]:
        """
        Parse reviewer errors into concrete modifications.

        Args:
            errors: List of error messages from reviewer
            user_prompt: Original user request (to infer values)

        Returns
        -------
            List of (parameter, value) tuples per PRD AgentState schema
        """
        fixes = []

        for error in errors:
            error_lower = error.lower()

            # Missing geometry.prob_lo
            if 'geometry.prob_lo' in error_lower and 'not specified' in error_lower:
                fixes.append(('geometry.prob_lo', '0 0 0'))

            # Missing geometry.prob_hi
            if 'geometry.prob_hi' in error_lower and 'not specified' in error_lower:
                # Try to infer from prompt
                domain_size = self._infer_domain_size(user_prompt)
                fixes.append(('geometry.prob_hi', domain_size))

            # Missing amr.n_cell
            if 'amr.n_cell' in error_lower and 'not specified' in error_lower:
                # Try to extract from prompt
                grid = self._extract_grid_from_prompt(user_prompt)

                if not grid:
                    # No grid in prompt - use sensible default based on 2D/3D
                    is_2d = '2d' in user_prompt.lower()
                    grid = [128, 128] if is_2d else [64, 64, 64]
                    logger.debug(f"      No grid size in prompt, using default: {grid}")

                grid_str = ' '.join(map(str, grid))
                fixes.append(('amr.n_cell', grid_str))

            # Missing geometry section entirely
            if 'geometry section missing' in error_lower:
                fixes.extend([
                    ('geometry.prob_lo', '0 0 0'),
                    ('geometry.prob_hi', self._infer_domain_size(user_prompt)),
                    ('geometry.is_periodic', '0 0 0'),
                ])

            # Missing amr section
            if 'amr section missing' in error_lower:
                grid = self._extract_grid_from_prompt(user_prompt)
                if grid:
                    grid_str = ' '.join(map(str, grid))
                    fixes.append(('amr.n_cell', grid_str))

        return fixes


    def _infer_domain_size(self, user_prompt: str) -> str:
        """Infer domain size from prompt or use sensible default."""
        # Look for explicit size mentions
        import re

        # Check for "X cm" or "X m" domain
        if match := re.search(r'(\d+\.?\d*)\s*(cm|m|mm)\s+domain', user_prompt.lower()):
            size = float(match.group(1))
            unit = match.group(2)

            # Convert to meters
            if unit == 'cm':
                size /= 100
            elif unit == 'mm':
                size /= 1000

            return f'{size} {size} {size}'  # Cubic domain

        # Check for "2D" vs "3D"
        is_2d = '2d' in user_prompt.lower()

        # Default: 10cm domain
        if is_2d:
            return '0.1 0.1 0.0'
        else:
            return '0.1 0.1 0.1'

    def _extract_grid_from_prompt(self, user_prompt: str) -> list[int] | None:
        """Extract grid size from prompt like '256x256' or '128x128x64'."""
        import re

        # Look for NxN or NxNxN patterns
        if match := re.search(r'(\d+)\s*[x×]\s*(\d+)(?:\s*[x×]\s*(\d+))?', user_prompt):
            grid = [int(match.group(1)), int(match.group(2))]
            if match.group(3):
                grid.append(int(match.group(3)))
            return grid

        return None

    def _parse_solver_from_answer(self, answer: str) -> str:
        """Extract solver choice from knowledge base answer."""
        answer_lower = answer.lower()

        # Check against available solvers
        code_registry = self.config.get_code_registry()
        for solver_name in code_registry:
            if solver_name.lower() in answer_lower:
                exclusions = get_solver_match_exclusions(solver_name)
                if any(exclusion in answer_lower for exclusion in exclusions):
                    continue
                return solver_name

        # Fallback: check for physics keywords
        # #######################
        # # Domain-specific: low-Mach/incompressible → solver mapping
        # #######################
        if 'low-mach' in answer_lower or 'incompressible' in answer_lower:
            solver = get_low_mach_solver(code_registry, None)
            if solver:
                return solver
        # #######################

        raise ValueError("Cannot determine solver from answer")

    def _parse_cfl_from_answer(self, answer: str) -> float:
        """Extract CFL number from knowledge base answer."""
        # Look for patterns like "CFL = 0.2" or "CFL of 0.1-0.2"
        cfl_match = re.search(r'CFL.*?(\d+\.?\d*)', answer, re.IGNORECASE)
        if cfl_match:
            return float(cfl_match.group(1))
        return 0.2  # safe default from Report 5

    def _gather_knowledge(self,
                         prompt: str,
                         requirements: dict) -> dict[str, Any]:
        """
        Query knowledge base for relevant information.

        Asks questions about:
        - Chemistry mechanisms
        - Grid requirements
        - Typical parameters for this problem type
        """
        knowledge = {}

        # Generate questions based on requirements
        questions = []

        if 'chemistry' in requirements:
            questions.append(f"What chemistry mechanism should I use for {requirements['chemistry']}?")

        if 'problem_type' in requirements:
            questions.append(f"What are typical parameters for {requirements['problem_type']} problems?")

        if 'max_level' in requirements:
            questions.append("What blocking factor should I use for AMR?")

        # Query knowledge base
        for question in questions:
            try:
                result = self.knowledge.query(question, context=requirements)
                knowledge[question] = result.get('answer', '')
            except Exception as e:
                logger.warning(f"[WARN] Knowledge query failed: {e}")

        return knowledge

    def _select_baseline(self,
        # DEPRECATED: Legacy 5-bucket heuristic
        # TODO: Migrate to select_baseline() (Architect Service: Baseline Selection RAG approach)
                         user_prompt: str,
                         requirements: dict[str, Any],
                         prefer_quality: str = "excellent",
                         weights: dict[str, float] | None = None) -> dict[str, Any] | None:
        """
        Four-approach configurable baseline selection.

        Scoring approaches:
        1. kb_relevance: Knowledge base physics/problem matching
        2. metrics: Objective git metrics (age, commits, size, position)
        3. path_heuristics: Generic path patterns (RegTest, Production)
        4. domain_specific: Combustion keywords, fuel matching

        Args:
            weights: Scoring approach weights (default: balanced)
        """
        # === PART 1: Setup Weights ===

        if weights is None:
            # Default weights for 5-bucket scoring system
            # FAISS semantic search added as 5th bucket for A/B comparison
            weights = {
                'kb_relevance': 0.40,
                'metrics': 0.25,
                'path_heuristics': 0.10,
                'domain_specific': 0.25,
                'faiss_semantic': self.config.faiss_semantic_weight  # 5th bucket (default 0.20)
            }

        # Normalize to sum to 1.0
        total = sum(weights.values())
        weights = {k: v/total for k, v in weights.items()}

        # Determine if using FAISS (5-bucket) or traditional (4-bucket)
        num_buckets = 5 if weights.get('faiss_semantic', 0) > 0 and self.embeddings and self.embeddings.indices_available() else 4

        logger.debug(f" Baseline selection with {num_buckets} scoring approaches")
        weights_msg = (f"       Weights: KB={weights['kb_relevance']:.0%}, "
                       f"Metrics={weights['metrics']:.0%}, "
                       f"Path={weights['path_heuristics']:.0%}, "
                       f"Domain={weights['domain_specific']:.0%}")
        if num_buckets == 5:
            weights_msg += f", FAISS={weights.get('faiss_semantic', 0):.0%}"
        logger.debug(weights_msg)

        # === Get code and cases (keep existing logic) ===

        # Stage 1: LLM picks CODE
        if self.llm_client:
            try:
                code_name, _ = self.cases.find_best_match(
                    user_prompt,
                    self.llm_client,
                    prefer_quality=prefer_quality
                )
                logger.debug(f" LLM selected code: {code_name}")
            except Exception as e:
                logger.warning(f"[WARN] LLM failed: {e}")
                code_name = requirements.get('solver')
                if not code_name:
                    raise ValueError(
                        f"LLM selection failed and no solver in requirements: {e}"
                    ) from e
        else:
            code_name = requirements.get('solver')
            if not code_name:
                raise ValueError("No solver specified in requirements and LLM path not taken")

        # Get all cases for this code
        all_cases = self.cases.list_all_cases()
        case_list = all_cases.get(code_name, [])

        if not case_list:
            logger.warning(f"[WARN] No cases found for {code_name}")
            return None

        logger.debug(f" Scoring {len(case_list)} {code_name} cases...")

        # === Get code definition and repo path ONCE ===
        code_def = self.cases.get_code_info(code_name)
        repo_path = code_def.local_path if code_def else None

        # === KB Batch Scoring (ONE query for all cases) ===

        kb_scores = {}
        if weights['kb_relevance'] > 0:
            kb_scores = self._score_kb_relevance_batch(
                case_list, user_prompt, requirements, code_name
            )

        # === PART 1: Build scoring matrix (skeleton) ===

        scoring_matrix = []

        for case_path in case_list:
            scores = {
                'case': case_path,
                'kb_relevance': 0.0,
                'metrics': 0.0,
                'path_heuristics': 0.0,
                'domain_specific': 0.0,
                'faiss_semantic': 0.0,  # 5th bucket
                'total': 0.0,
                'details': {}
            }

            # === Build scoring matrix ===
            # PART 2: KB Relevance (IMPLEMENTED)
            if weights['kb_relevance'] > 0:
                kb_score = kb_scores.get(case_path, 0.2)
                #kb_score = self._score_kb_relevance(
                #    case_path, user_prompt, requirements, code_name
                #)
                scores['kb_relevance'] = kb_score
                scores['total'] += kb_score * weights['kb_relevance']

            # PART 3: Metrics (IMPLEMENTED)
            if weights['metrics'] > 0:
                metric_score, metric_details = self._score_metrics(
                    case_path,
                    code_def,
                    repo_path=repo_path
                )
                scores['metrics'] = metric_score
                scores['details']['metrics'] = metric_details
                scores['total'] += metric_score * weights['metrics']

            # PART 4: Path Heuristics (IMPLEMENTED)
            if weights['path_heuristics'] > 0:
                path_score, path_details = self._score_path_heuristics(
                    case_path,
                    code_def
                )
                scores['path_heuristics'] = path_score
                scores['details']['path'] = path_details
                scores['total'] += path_score * weights['path_heuristics']

            # PART 5: Domain-Specific (IMPLEMENTED)
            if weights['domain_specific'] > 0:
                domain_score, domain_details = self._score_combustion_domain(
                    case_path,
                    requirements,
                    code_def  # Pass code_def for mechanism extraction
                )
                scores['domain_specific'] = domain_score
                scores['details']['domain'] = domain_details
                scores['total'] += domain_score * weights['domain_specific']

            # PART 6: FAISS Semantic Search (NEW - 5th bucket)
            # Note: This is computed once for all cases below, not per-case
            # Placeholder here, actual computation happens in batch after loop

            scoring_matrix.append(scores)

        # === PART 6: FAISS Semantic Scoring (Batch computation for all cases) ===
        if weights.get('faiss_semantic', 0) > 0 and self.embeddings and self.embeddings.indices_available():
            faiss_scores = self._score_faiss_semantic_batch(
                case_list, user_prompt, requirements, code_name
            )

            # Update scoring matrix with FAISS scores
            for score_entry in scoring_matrix:
                case_path = score_entry['case']
                faiss_score = faiss_scores.get(case_path, 0.0)
                score_entry['faiss_semantic'] = faiss_score
                score_entry['total'] += faiss_score * weights['faiss_semantic']

        # === Rank and return ===

        scoring_matrix.sort(key=lambda x: x['total'], reverse=True)

        if scoring_matrix:
            winner = scoring_matrix[0]
            for entry in scoring_matrix[:10]:
                case_name = Path(entry['case']).name
                logger.debug(f"  {case_name:30s} total={entry['total']:.3f} "
                      f"(FAISS={entry.get('faiss_semantic', 0):.3f}, "
                      f"metrics={entry.get('metrics', 0):.3f}, "
                      f"path={entry.get('path_heuristics', 0):.3f}, "
                      f"domain={entry.get('domain_specific', 0):.3f})")

                # Also debug Sedov specifically
                sedov_entry = next((e for e in scoring_matrix if 'Sedov' in e['case']), None)
                if sedov_entry:
                    logger.debug("\n[DEBUG] Sedov final breakdown:")
                    logger.debug(f"  total: {sedov_entry['total']:.3f}")
                    logger.debug(f"  faiss_semantic: {sedov_entry.get('faiss_semantic', 0):.3f} (weight: {weights['faiss_semantic']:.0%})")
                    logger.debug(f"  metrics: {sedov_entry.get('metrics', 0):.3f} (weight: {weights['metrics']:.0%})")
                    logger.debug(f"  path_heuristics: {sedov_entry.get('path_heuristics', 0):.3f} (weight: {weights['path_heuristics']:.0%})")
                    logger.debug(f"  domain_specific: {sedov_entry.get('domain_specific', 0):.3f} (weight: {weights['domain_specific']:.0%})")

            baseline = {
                'code': code_name,
                'path': winner['case'],
                'name': f"{code_name}/{winner['case']}",
                'match_score': winner['total'],
                'match_rationale': f"{num_buckets}-bucket scoring (weights: {weights})",
                'scoring_matrix': scoring_matrix[:5],
                'weights_used': weights
            }
            code_def = self.cases.get_code_info(code_name)

            if code_def and code_def.local_path:
                baseline['repo_path'] = str(code_def.local_path)
            else:
                baseline['repo_path'] = None

            return baseline

        return None

    def _score_kb_relevance_batch(self,
                                  case_list: list[str],
                                  user_prompt: str,
                                  requirements: dict,
                                  code_name: str) -> dict[str, float]:
        """
        Score all cases in ONE query with nuanced 0-10 ratings.

        Much faster than per-case queries, more discriminating than simple ranking.

        Returns
        -------
            Dict mapping case_path -> score (0.0-1.0)
        """
        problem_type = self._infer_problem_type(user_prompt, requirements)
        dimensionality = f"{len(requirements.get('grid', [0,0]))}D"

        # Build case list for display
        case_names = [case.split('/')[-1] for case in case_list[:15]]  # Limit to 15
        # === CLEAN SEMANTIC QUERY (for embedding/FAISS) ===
        semantic_query = f"""Simulation request: {user_prompt}

Physics: {requirements.get('physics', 'fluid dynamics')}
Problem type: {problem_type}
Dimensionality: {dimensionality}
Solver: {code_name}"""

        try:
            # Use semantic query for FAISS search
            answer = self.knowledge.query(
                semantic_query,
                context={
                    'cases': case_names,
                    'code': code_name,
                    'use_instruction': False  # Flag to skip instruction wrapper
                }
            )
            logger.debug(
                "KB batch answer keys=%s method=%s confidence=%s",
                list(answer.keys()),
                answer.get("method"),
                answer.get("confidence"),
            )
            if answer.get("answer"):
                logger.debug("KB batch answer preview: %s", str(answer.get("answer"))[:200])

            # === FAISS PATH: Convert sources to scores ===
            if answer.get('method') == 'faiss' and answer.get('sources') and 'scores' not in answer:
                logger.debug(" Using FAISS semantic scores")
                scores = {}
                case_path = None  # Initialize to prevent UnboundLocalError

                for source in answer.get('sources', []):
                    case_path = source.get('case')
                    distance = source.get('score', 10.0)  # L2 distance (lower=better)

                    if case_path:
                        # Convert distance to similarity using exponential decay
                        # Typical L2 distances are 0.8-1.5, so exp(-distance) works well
                        similarity = math.exp(-distance)
                        # Or use: similarity = 1.0 / (1.0 + distance)

                        scores[case_path] = similarity

                # Cases not retrieved
                for case in case_list:
                    if case not in scores:
                        scores[case] = 0.0  # Not retrieved = not relevant

                logger.debug(f" FAISS scored {len(scores)} cases")

                # Show top FAISS scores
                top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
                logger.debug(" Top FAISS scores:")
                for case, score in top:
                    case_name = case.split('/')[-1]
                    logger.debug(f"  {score:.3f} - {case_name}")

                return scores

            # === LLM PATH: Parse JSON scores ===
            elif 'answer' in answer:
                logger.debug(" Using LLM JSON scores")
                import json
                import re

                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', answer['answer'], re.DOTALL)
                if json_match:
                    scores_dict = json.loads(json_match.group(0))

                    # Map to full paths and normalize to 0-1
                    result = {}
                    for case_path in case_list:
                        case_name = case_path.split('/')[-1]

                        # Try exact match
                        if case_name in scores_dict:
                            score = float(scores_dict[case_name])
                            result[case_path] = min(1.0, max(0.0, score / 10.0))
                        # Try fuzzy match
                        else:
                            matched = False
                            for key in scores_dict:
                                if case_name.lower() in key.lower() or key.lower() in case_name.lower():
                                    score = float(scores_dict[key])
                                    result[case_path] = min(1.0, max(0.0, score / 10.0))
                                    matched = True
                                    break

                            if not matched:
                                # Not found - use fallback
                                result[case_path] = self._score_kb_relevance_fallback(
                                    case_path, problem_type, requirements
                                )

                    logger.debug(f" LLM scored {len(result)} cases")
                    return result
                else:
                    raise ValueError("No JSON in LLM response")

            else:
                raise ValueError("Unknown KB result format")

        except Exception as e:
            logger.warning(f"[WARN] KB batch scoring failed: {e}")

            # Fallback: keyword matching for all cases
            result = {}
            for case_path in case_list:
                result[case_path] = self._score_kb_relevance_fallback(
                    case_path, problem_type, requirements
                )
            return result


    def _score_kb_relevance_fallback(self, case_path: str,
                                     problem_type: str,
                                     requirements: dict) -> float:
        """Fallback keyword-based scoring if KB fails."""
        case_lower = case_path.lower()

        # Problem type match
        if problem_type and problem_type.lower().split()[0] in case_lower:
            return 0.7

        # Physics keywords
        physics = requirements.get('physics', '').lower()
        physics_map = {
            'combustion': ['flame', 'pmf', 'react', 'combust'],
            'vortex': ['vortex', 'tg', 'taylor'],
            'shock': ['shock', 'blast', 'sedov'],
        }

        for phys_type, keywords in physics_map.items():
            if phys_type in physics:
                for kw in keywords:
                    if kw in case_lower:
                        return 0.5

        return 0.2  # Default low

    def _score_kb_relevance(self,
                           case_path: str,
                           user_prompt: str,
                           requirements: dict,
                           code_name: str) -> float:
        """
        Score case relevance using knowledge base.

        GENERIC - uses domain-agnostic concepts:
        - Problem type (flame, vortex, shock, boundary layer, etc.)
        - Flow regime (compressible, turbulent, steady, etc.)
        - Dimensionality (2D, 3D)
        - Physics features (reactive, multiphase, etc.)

        Domain-specific details (fuel, chemistry, etc.) -> domain_specific scoring

        Returns
        -------
            0.0-1.0 score based on problem similarity
        """
        case_name = case_path.split('/')[-1]

        # Extract GENERIC problem characteristics
        problem_type = self._infer_problem_type(user_prompt, requirements)
        flow_regime = requirements.get('solver', 'compressible')
        dimensionality = '3D' if len(requirements.get('grid', [0,0,0])) == 3 else '2D'
        physics = requirements.get('physics', 'fluid dynamics')

        # Build generic question
        question = f"""Rate the relevance of the '{case_name}' example case for this simulation:

    Problem: {user_prompt}

    Generic characteristics:
    - Problem type: {problem_type}
    - Flow regime: {flow_regime}
    - Dimensionality: {dimensionality}
    - Physics: {physics}

    On a scale of 0-10, how relevant is '{case_name}' as a starting point?
    Focus on problem structure and physics similarity (ignore specific materials/fuels).

    Return ONLY a number between 0-10."""

        try:
            answer = self.knowledge.query(question, context={'case': case_name, 'prompt': user_prompt})

            import re
            match = re.search(r'(\d+(?:\.\d+)?)', answer['answer'])
            if match:
                rating = float(match.group(1))
                return min(1.0, max(0.0, rating / 10.0))

        except Exception as e:
            logger.warning(f"[WARN] KB scoring failed for {case_name}: {e}")

        # Fallback: generic keyword matching
        case_lower = case_name.lower()
        # Problem type matching
        if problem_type and problem_type.lower() in case_lower:
            return 0.7

        # Physics type matching
        physics_keywords = {
            'combustion': ['flame', 'react', 'combust', 'burn', 'pmf'],
            'shock': ['shock', 'blast', 'sedov', 'detonation'],
            'vortex': ['vortex', 'tg', 'taylor', 'hit'],
            'boundary layer': ['boundary', 'abl', 'wall'],
            'jet': ['jet', 'mixing', 'injection'],
        }

        for physics_type, keywords in physics_keywords.items():
            if physics_type in physics.lower():
                for keyword in keywords:
                    if keyword in case_lower:
                        return 0.5

        return 0.2


    def _infer_problem_type(self, prompt: str, requirements: dict) -> str:
        """
        Infer GENERIC problem type from prompt.

        Returns generic descriptors, not domain-specific terms.
        Examples: "premixed flame", "vortex", "shock wave", "jet flow"
        """
        prompt_lower = prompt.lower()

        # Generic flow patterns
        if any(word in prompt_lower for word in ['vortex', 'taylor-green', 'tg']):
            return "vortex flow"

        if any(word in prompt_lower for word in ['shock', 'blast', 'sedov']):
            return "shock wave"

        if any(word in prompt_lower for word in ['jet', 'injection', 'spray']):
            return "jet flow"

        if any(word in prompt_lower for word in ['boundary layer', 'abl', 'wall']):
            return "boundary layer"

        # Reactive vs non-reactive (generic)
        if requirements.get('physics') == 'combustion' or any(
            word in prompt_lower for word in ['flame', 'burn', 'react']
        ):
            # Still generic - type of flame, not fuel-specific
            if 'premix' in prompt_lower or 'pmf' in prompt_lower:
                return "premixed flame"
            elif 'diffusion' in prompt_lower or 'counter' in prompt_lower:
                return "diffusion flame"
            else:
                return "reactive flow"

        # Default
        return "general flow"

    def _score_metrics(self,
                       case_path: str,
                       code_def,
                       repo_path: Path | None
                       ) -> tuple[float, dict]:
        """
        Compute objective git-based quality metrics.

        Sub-metrics (equal weight):
        - Git age (older = more mature)
        - Commit count (more = better tested)
        - File size (shorter = simpler baseline)
        - Position in common_cases (earlier = more common)

        Args:
            case_path: Relative path like 'Exec/RegTests/FlameSheet'
            repo_path: Absolute path to repo
            code_def: Code definition (for common_cases position)

        Returns
        -------
            (total_score, details_dict)
        """
        details = {}
        total = 0.0

        # If no local repo, return neutral
        if not repo_path or not repo_path.exists():
            repo_path = code_def.local_path if code_def else None
            if not repo_path or not repo_path.exists():
                return 0.5, {'no_local_repo': True}

        case_dir = repo_path / case_path

        # Sub-metric 1: Git age (25%)
        age_score = self._score_by_git_age(case_dir)
        details['age'] = age_score
        total += age_score * 0.25

        # Sub-metric 2: Commit count (25%)
        commit_score = self._score_by_commit_count(case_dir)
        details['commits'] = commit_score
        total += commit_score * 0.25

        # Sub-metric 3: File size (25%)
        size_score = self._score_by_file_size(case_dir)
        details['size'] = size_score
        total += size_score * 0.25

        # Sub-metric 4: Position in common_cases (25%)
        if code_def and case_path in code_def.common_cases:
            position = code_def.common_cases.index(case_path)
            pos_score = 1.0 - (position / len(code_def.common_cases))
            details['position'] = pos_score
            total += pos_score * 0.25
        else:
            # Not in common_cases - neutral
            details['position'] = 0.5
            total += 0.125

        return total, details


    def _score_by_git_age(self, case_dir: Path) -> float:
        """
        Score by file age (older = more mature).

        Returns 0.0-1.0 where 1.0 = very old (5+ years)
        """
        import subprocess

        if not case_dir.exists():
            return 0.5  # Neutral if doesn't exist

        try:
            # Get first commit date of inputs file in this directory
            result = subprocess.run(
                ['git', 'log', '--format=%aI', '--diff-filter=A', '--reverse', '--', 'inputs*', '*.inp'],
                cwd=case_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                first_commit = result.stdout.strip().split('\n')[0]
                commit_date = datetime.fromisoformat(first_commit.replace('Z', '+00:00'))
                age_years = (datetime.now(commit_date.tzinfo) - commit_date).days / 365.25

                # Normalize: 5+ years = 1.0, 0 years = 0.0
                return min(1.0, age_years / 5.0)

        except Exception:
            pass

        return 0.5  # Default neutral


    def _score_by_commit_count(self, case_dir: Path) -> float:
        """
        Score by number of commits (more = better tested).

        Returns 0.0-1.0 where 1.0 = 50+ commits
        """
        import subprocess

        if not case_dir.exists():
            return 0.5

        try:
            result = subprocess.run(
                ['git', 'log', '--oneline', '--', 'inputs*', '*.inp'],
                cwd=case_dir,
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and result.stdout.strip():
                commit_count = len(result.stdout.strip().split('\n'))

                # Normalize: 50+ commits = 1.0, 0 = 0.0
                return min(1.0, commit_count / 50.0)

        except Exception:
            pass

        return 0.5


    def _score_by_file_size(self, case_dir: Path) -> float:
        """
        Score by inputs file size (shorter = simpler).

        Returns 0.0-1.0 where 1.0 = very short (<5KB)
        """
        if not case_dir.exists():
            return 0.5

        try:
            # Find inputs file
            # Use config-based patterns
            from database.configs import get_config_for_path
            config_cls = get_config_for_path(str(case_dir))
            inputs_files = config_cls.find_inputs_files(case_dir)

            if inputs_files:
                # Use first non-backup file
                for f in inputs_files:
                    if not f.name.endswith(('.bak', '~', '.old')):
                        size_kb = f.stat().st_size / 1024

                        # Normalize: <5KB = 1.0, >20KB = 0.0
                        # Smaller is better for baseline
                        if size_kb < 5:
                            return 1.0
                        elif size_kb > 20:
                            return 0.0
                        else:
                            return 1.0 - ((size_kb - 5) / 15)

        except Exception:
            pass

        return 0.5

    def _score_path_heuristics(self, case_path: str, code_def) -> tuple[float, dict]:
        """
        Path-based quality scoring for AMReX codes.

        Strategy:
        1. Check if under Exec/ or Examples/
        2. Look at subdirectories for quality indicators
        3. Check input filename for quality suffixes
        """
        repo_path = code_def.local_path if code_def else None

        path_lower = case_path.lower()
        path_parts = [p.lower() for p in case_path.split('/')]

        # Get filename if it's an input file
        filename = path_parts[-1] if path_parts else ''

        score = 0.5  # default
        details = {}

        # === Check repo structure (if we have it) ===
        has_production_dir = False
        if repo_path and repo_path.exists():
            has_production_dir = (repo_path / 'Exec' / 'Production').exists() or \
                (repo_path / 'Exec' / 'production').exists()
            details['repo_has_production'] = has_production_dir

        # === Check subdirectories under Exec ===
        if 'exec' in path_parts:
            exec_idx = path_parts.index('exec')
            subdirs_after = '/'.join(path_parts[exec_idx+1:])

            # Regression tests = highest quality
            if 'regression' in subdirs_after or 'regtest' in subdirs_after:
                score = 0.85
                details['type'] = 'Exec/Regression'

            elif 'benchmark' in subdirs_after:
                score = 0.8  # Between regression and production
                details['type'] = 'Exec/Benchmark'

            # Production/Science = high quality
            elif 'production' in subdirs_after or 'science' in subdirs_after:
                score = 0.75
                details['type'] = 'Exec/Production'

            # Test directories (reacting_tests, hydro_tests, etc.)
            elif 'test' in subdirs_after:
                score = 0.7
                details['type'] = 'Exec/Tests'

            # Tutorials/Examples under Exec = learning-focused
            elif 'tutorial' in subdirs_after or 'example' in subdirs_after:
                score = 0.4
                details['type'] = 'Exec/Tutorial'

            # Generic Exec
            else:
                if has_production_dir:
                    score = 0.6
                    details['type'] = 'Exec/Unknown'
                else:
                    score = 0.75  # No Production dir → these ARE production
                    details['type'] = 'Exec/ImpliedProduction'

        # === Check subdirectories under Examples ===
        elif 'example' in path_parts or 'examples' in path_parts:
            example_idx = next(i for i, p in enumerate(path_parts) if 'example' in p)
            subdirs_after = '/'.join(path_parts[example_idx+1:])

            # Tests under Examples
            if 'test' in subdirs_after:
                score = 0.65
                details['type'] = 'Examples/Tests'

            # Regular examples
            else:
                score = 0.4
                details['type'] = 'Examples'

        # === Standalone quality indicators (not under Exec/Examples) ===
        elif 'regression' in path_lower or 'regtest' in path_lower:
            score = 0.85
            details['type'] = 'Regression'

        elif 'benchmark' in path_lower:
            score = 0.8
            details['type'] = 'Benchmark'


        elif any(p in path_parts for p in ['test', 'tests', 'unit_tests']):
            score = 0.7
            details['type'] = 'Tests'

        else:
            score = 0.5
            details['type'] = 'Unknown'

        # === Boost score for regression/CI input filenames ===
        if '.regt' in filename or '-rt' in filename or 'inputs.rt' in filename:
            score = min(score + 0.1, 1.0)
            details['filename_boost'] = 'regression_test'
        elif '-ci' in filename or 'inputs-ci' in filename:
            score = min(score + 0.05, 1.0)
            details['filename_boost'] = 'ci_test'

        return score, details

    def _score_combustion_domain(self, case_path: str, requirements: dict,
                                 code_def) -> tuple[float, dict]:
        """
        DOMAIN-SPECIFIC: Combustion-focused scoring with mechanism-fuel matching.

        Uses actual chemistry mechanism from GNUmakefile/CMakeLists to match fuel.

        Returns
        -------
            (score, details_dict)
        """
        case_lower = case_path.lower()
        score = 0.0
        details = {}

        domain_data = {}
        if code_def and hasattr(code_def, "get_domain_data"):
            domain_data = code_def.get_domain_data()

        # === 1. Flame Configuration (40% of domain score) ===
        flame_configs = domain_data.get('flame_configs', {})

        for config, config_score in flame_configs.items():
            if config in case_lower:
                score += config_score
                details['flame_config'] = config
                break

        # === 2. Spray/Multiphase (20% of domain score) ===
        if 'spray' in case_lower:
            score += 0.20
            details['multiphase'] = 'spray'
        elif 'droplet' in case_lower:
            score += 0.15
            details['multiphase'] = 'droplet'

        # === 3. Physics Problem Types (20% of domain score) ===
        physics_problems = domain_data.get('physics_problems', {})

        for problem, problem_score in physics_problems.items():
            if problem in case_lower:
                score += problem_score
                details['physics_problem'] = problem
                break

        problem_type = requirements.get('problem_type', '')
        if problem_type.startswith('jet') and 'jet' in case_lower:
            score = max(score, 1.0)
            details['problem_type_match'] = problem_type


        # === 4. MECHANISM-FUEL MATCHING (20% of domain score) ===
        # Extract mechanism from case directory
        mechanism = None
        if code_def and code_def.local_path:
            case_dir = code_def.local_path / case_path
            mechanism = self._extract_mechanism_from_makefile(case_dir)

        requested_fuel = requirements.get('fuel', '').lower()

        if mechanism and requested_fuel:
            mechanisms = domain_data.get('mechanisms', {})
            fuels_for_mechanism = mechanisms.get(mechanism, [])

            # Exact fuel match
            if requested_fuel in fuels_for_mechanism:
                score += 0.20
                details['mechanism_fuel_match'] = f'{mechanism} → {requested_fuel}'

            # Partial match (e.g., 'h2' matches 'hydrogen')
            elif any(fuel in requested_fuel or requested_fuel in fuel
                     for fuel in fuels_for_mechanism):
                score += 0.10
                details['mechanism_fuel_partial'] = f'{mechanism} ≈ {requested_fuel}'

        # Fallback: Mechanism in case name (if we couldn't extract)
        elif not mechanism and requested_fuel:
            # Try to infer mechanism from case name
            mechanisms = domain_data.get('mechanisms', {})
            for mech, fuels in mechanisms.items():
                if mech in case_lower and requested_fuel in fuels:
                    score += 0.15
                    details['inferred_mechanism_match'] = mech
                    break

        # Normalize to 0-1
        score = min(1.0, score)

        if mechanism:
            details['mechanism_detected'] = mechanism

        return score, details

    def _score_faiss_semantic_batch(self,
                                     case_list: list[str],
                                     user_prompt: str,
                                     requirements: dict,
                                     code_name: str) -> dict[str, float]:
        """
        Score all cases using FAISS semantic similarity (5th scoring bucket).

        Implements foam-agent's hierarchical retrieval pattern:
        1. Query case_structure index (broad matching)
        2. Query case_details index (detailed matching)
        3. Combine scores with weighted averaging

        Args:
            case_list: List of case paths to score
            user_prompt: Original user request
            requirements: Extracted requirements dict
            code_name: AMReX application code name

        Returns
        -------
            Dict mapping case_path -> score (0.0-1.0)
        """
        if not self.embeddings or not self.embeddings.indices_available():
            return dict.fromkeys(case_list, 0.0)

        # Build search query from user prompt and requirements
        search_query = self._build_faiss_query(user_prompt, requirements)

        logger.debug(f"[DEBUG] FAISS search query: {search_query}")

        # Determine which indices to use based on code
        code_lower = code_name.lower()
        names_index = f"{code_lower}_case_names"
        structure_index = f"{code_lower}_case_structure"
        details_index = f"{code_lower}_case_details"

        # === Hierarchical retrieval across 3 levels ===

        # Level 1: Fast name/directory matching (NEW)
        try:
            names_results = self.embeddings.retrieve_faiss(
                search_query,
                names_index,
                topk=min(50, len(case_list) * 2)
            )
            logger.debug(f"[DEBUG] Names index: {names_index}")
            logger.debug(f"[DEBUG] Names results: {len(names_results.get('results', []))} items")
            # Show top 5 from names
            for i, result in enumerate(names_results.get('results', [])[:5], 1):
                case = result.get('metadata', {}).get('case', 'unknown')
                score = result.get('score', 0)
                logger.debug(f"  {i}. {case:30s} score={score:.3f}")
        except Exception as e:
            logger.debug(f"Warning: FAISS {names_index} query failed: {e}")
            names_results = {'results': []}

        # Level 2: Broad case structure
        try:
            structure_results = self.embeddings.retrieve_faiss(
                search_query,
                structure_index,
                topk=min(50, len(case_list) * 2)
            )
            logger.debug(f"[DEBUG] Structure index: {structure_index}")
            logger.debug(f"[DEBUG] Structure results: {len(structure_results.get('results', []))} items")
            # Show top 5
            for i, result in enumerate(structure_results.get('results', [])[:5], 1):
                case = result.get('metadata', {}).get('case', 'unknown')
                score = result.get('score', 0)
                logger.debug(f"  {i}. {case:30s} score={score:.3f}")
        except Exception as e:
            logger.debug(f"Warning: FAISS {structure_index} query failed: {e}")
            structure_results = {'results': []}

        # Level 3: Detailed README content
        try:
            details_results = self.embeddings.retrieve_faiss(
                search_query,
                details_index,
                topk=min(50, len(case_list))
            )
        except Exception as e:
            logger.debug(f"Warning: FAISS {details_index} query failed: {e}")
            details_results = {'results': []}

        # === Score combination with weights ===
        weights = {
            'names': 0.70,      # Fast name/directory matching
            'structure': 0.15,  # High-level descriptions
            'details': 0.10     # Detailed semantic content
        }

        scores = {}
        for case_path in case_list:
            # Get score from each index
            names_score = self._find_case_in_faiss_results(
                case_path, names_results.get('results', [])
            ) or 0.0

            structure_score = self._find_case_in_faiss_results(
                case_path, structure_results.get('results', [])
            ) or 0.0

            details_score = self._find_case_in_faiss_results(
                case_path, details_results.get('results', [])
            ) or 0.0

            # Weighted combination
            combined_score = (
                names_score * weights['names'] +
                structure_score * weights['structure'] +
                details_score * weights['details']
            )

            scores[case_path] = combined_score

            if 'Sedov' in case_path:
                logger.debug("[DEBUG] Sedov hierarchical scores:")
                logger.debug(f"  case_path: {case_path}")
                logger.debug(f"  names: {names_score:.3f}")
                logger.debug(f"  structure: {structure_score:.3f}")
                logger.debug(f"  details: {details_score:.3f}")
                logger.debug(f"  combined: {combined_score:.3f}")

        # Debug: Show top FAISS scores
        logger.debug("\n[SCAN] FAISS RAW SCORES (top 10):")
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for case_path, score in sorted_scores[:10]:
            case_name = Path(case_path).name
            logger.debug(f"  {case_name:30s} {score:.3f}")

        return scores

    def _build_faiss_query(self, user_prompt: str, requirements: dict) -> str:
        """
        Build optimized search query for FAISS from user prompt and requirements.

        Args:
            user_prompt: Original user request
            requirements: Extracted requirements

        Returns
        -------
            Enhanced query string
        """
        # Start with user prompt
        query_parts = [user_prompt]

        # Add key requirements for better matching
        if requirements.get('fuel'):
            query_parts.append(f"fuel: {requirements['fuel']}")

        if requirements.get('mechanism'):
            query_parts.append(f"mechanism: {requirements['mechanism']}")

        if requirements.get('physics'):
            query_parts.append(f"physics: {requirements['physics']}")

        if requirements.get('problem_type'):
            query_parts.append(f"problem: {requirements['problem_type']}")

        return ' '.join(query_parts)

    def _find_case_in_faiss_results(self, case_path: str, results: list[dict]) -> float | None:
        """
        Find case in FAISS results and convert distance to similarity score.

        FAISS returns distance scores (lower is better).
        We convert to similarity scores (higher is better, 0-1 range).

        Args:
            case_path: Case path to find
            results: FAISS results list

        Returns
        -------
            Similarity score (0-1) or None if not found
        """
        for result in results:
            metadata = result.get('metadata', {})
            result_path = metadata.get('case', '')
            result_name = metadata.get('case_name', '')

            # Match by case_path or case_name
            if case_path in result_path or case_path.endswith(result_name):
                # Convert FAISS distance to similarity score
                # Lower distance = higher similarity
                distance = result.get('score', float('inf'))

                # Convert distance to similarity (0-1 range)
                # Use exponential decay: score = exp(-distance)
                # This maps: distance 0 → score 1.0, distance 1 → score 0.37, distance 2 → score 0.14
                import math
                similarity = math.exp(-distance)

                return similarity

        return None


    def _extract_mechanism_from_makefile(self, case_dir: Path) -> str | None:
        """
        Extract Chemistry_Model from GNUmakefile or CMakeLists.txt.

        Looks for patterns like:
        - Chemistry_Model = drm19
        - set(PELE_PHYSICS_CHEMISTRY_MODEL lidryer)
        """
        if not case_dir.exists():
            return None

        files_to_check = [
            ('GNUmakefile', ['chemistry_model']),
            ('CMakeLists.txt', ['pele_physics_chemistry_model', 'pele_chemistry_model']),
        ]

        for filename, variable_names in files_to_check:
            # Check case dir and parent dir
            for check_dir in [case_dir, case_dir.parent]:
                filepath = check_dir / filename

                if not filepath.exists():
                    continue

                try:
                    with open(filepath) as f:
                        for line in f:
                            line_lower = line.lower().strip()

                            # Skip comments
                            if line_lower.startswith('#'):
                                continue

                            # Check for any variable name
                            for var in variable_names:
                                if var in line_lower:
                                    # Extract value after = or := or in set()
                                    for sep in ['=', ':=', '(']:
                                        if sep in line:
                                            parts = line.split(sep, 1)
                                            if len(parts) > 1:
                                                mechanism = parts[1].strip()

                                                # Clean up
                                                mechanism = mechanism.split('#')[0].strip()
                                                mechanism = mechanism.strip('"\')')
                                                mechanism = mechanism.split('/')[-1]  # Remove paths
                                                mechanism = mechanism.lower()

                                                if mechanism and mechanism != '':
                                                    return mechanism
                except Exception:
                    continue

        return None

    def _parse_case_name_from_answer(self, answer: str) -> str | None:
        """Extract case name from knowledge base answer."""
        # Look for common case patterns: RCCI, ODW, Supersonic Cavity, etc.
        case_patterns = [
            'rcci', 'odw', 'oblique detonation', 'cavity', 'supersonic',
            'micromix', 'premix', 'spray', 'engine', 'flame-holder'
        ]

        answer_lower = answer.lower()
        for pattern in case_patterns:
            if pattern in answer_lower:
                return pattern

        return None

    def _plan_modifications(self, requirements: dict, baseline: dict,
                           knowledge: list) -> list[tuple[str, Any]]:
        """Plan modifications with knowledge-based constraint validation."""
        modifications = []

        # Grid modification
        if requirements.get('grid'):
            section = 'amr'
            param = 'n_cell'

            constraint_q = f"If I set {section}.{param} = {requirements['grid']}, what blocking_factor values are valid?"
            constraint_answer = self.knowledge.query(constraint_q)

            modifications.append({
                'file': 'inputs',
                'parameter': f'{section}.{param}',
                'old_value': baseline.get('grid', [64, 64, 64]),
                'new_value': ' '.join(str(x) for x in requirements['grid']),
                'rationale': f"User-specified grid. {constraint_answer['answer'][:100]}"
            })

        solver = requirements.get('solver')
        ode_plan = get_solver_ode_tolerance_plan(solver) if solver else None
        if ode_plan:
            section = ode_plan["section"]
            param = ode_plan["param"]
            ode_q = ode_plan["prompt"].format(section=section, param=param)
            ode_answer = self.knowledge.query(ode_q)

            modifications.append({
                'file': 'inputs',
                'parameter': f'{section}.{param}',
                'old_value': ode_plan["old_value"],
                'new_value': ode_plan["new_value"],
                'rationale': f"Low-Mach QSSA requirement: {ode_answer['answer'][:100]}"
            })

        # #######################
        # # Domain-specific: CFL parameter location differs by solver family
        # #######################
        # CFL modification
        if requirements.get('recommended_cfl'):
            if not solver:
                logger.warning("Cannot apply CFL modification: no solver specified")
            else:
                param_name = get_cfl_param_name(solver)
                if not self._schema_has_param(solver, param_name):
                    logger.warning(
                        f"Skipping CFL modification: {param_name} not in {solver} schema"
                    )
                    param_name = None
                if not param_name:
                    pass
                elif '.' not in param_name:
                    logger.warning("Cannot apply CFL modification: invalid parameter mapping")
                else:
                    section, param = param_name.split('.', 1)
                    modifications.append({
                        'file': 'inputs',
                        'parameter': f'{section}.{param}',
                        'old_value': baseline.get('cfl', 0.5),
                        'new_value': str(requirements['recommended_cfl']),
                        'rationale': requirements.get('solver_rationale', 'Knowledge-based CFL')[:100]
                    })
        # #######################

        tier1_overrides = self._extract_tier1_overrides(
            prompt=requirements.get('user_prompt', ''),
            solver_name=solver,
            solver_config=self.code_configs.get(solver),
        )
        existing_params = {mod['parameter'] for mod in modifications}
        for param, value in tier1_overrides:
            if param in existing_params:
                continue
            modifications.append({
                'file': 'inputs',
                'parameter': param,
                'old_value': baseline.get(param),
                'new_value': str(value),
                'rationale': "Tier-1 parameter override from prompt"
            })
            existing_params.add(param)

        # Convert to tuple format per PRD AgentState schema
        return [(mod['parameter'], mod['new_value']) for mod in modifications]

    def _plan_visualization(self, requirements: dict, baseline: dict) -> dict:
        """
        Determine visualization configuration from user requirements.

        Extracts visualization intent from prompt:
        - "show temperature" → temperature slice plot
        - "visualize flame structure" → Temp + species slices
        - "plot velocity field" → velocity magnitude slice
        - "compare different timesteps" → timesteps = 'all'

        Args:
            requirements: User requirements dict
            baseline: Selected baseline case

        Returns
        -------
            Visualization configuration dict
        """
        vis_config = {
            'enabled': True,
            'backend': 'yt',  # Phase 4: yt-only
            'plots': [],
            'timesteps': 'latest',
            'format': 'png',
            'container_mode': self.config.environment in ['perlmutter', 'mcp']
        }

        prompt = requirements.get('user_prompt', '').lower()

        # Temperature (common for combustion)
        if any(kw in prompt for kw in ['temperature', 'temp', 'flame', 'heat']):
            vis_config['plots'].append({
                'type': 'slice',
                'field': 'Temp',
                'axis': 'z',
                'colormap': 'hot'
            })

        # Density
        if 'density' in prompt or 'rho' in prompt:
            vis_config['plots'].append({
                'type': 'slice',
                'field': 'density',
                'axis': 'z',
                'colormap': 'viridis'
            })

        # Velocity
        if any(kw in prompt for kw in ['velocity', 'flow', 'speed']):
            vis_config['plots'].append({
                'type': 'slice',
                'field': 'velocity_magnitude',
                'axis': 'z',
                'colormap': 'plasma'
            })

        # Species (if reactions enabled)
        solver_name = (
            baseline.get('code_name')
            or baseline.get('code')
            or baseline.get('metadata', {}).get('code')
            or requirements.get('solver')
        )
        solver_config = self.code_configs.get(solver_name) if solver_name else None
        reaction_flag_keys = get_reaction_flag_keys(solver_name) if solver_name else []
        inputs_content = baseline.get('metadata', {}).get('inputs_content', {})
        reactions_enabled = False
        for flag_key in reaction_flag_keys:
            if flag_key in inputs_content:
                reactions_enabled = str(inputs_content.get(flag_key)) == "1"
                break

        if not reactions_enabled and solver_config:
            section_key = solver_config.code_name.lower()
            section = baseline.get(section_key, {})
            if isinstance(section, dict):
                reactions_enabled = str(section.get("use_reactions", "0")) == "1"

        if reactions_enabled:
            fuel = requirements.get('fuel', 'CH4')
            if 'species' in prompt or fuel.lower() in prompt:
                vis_config['plots'].append({
                    'type': 'slice',
                    'field': f'Y({fuel})',
                    'axis': 'z',
                    'colormap': 'RdYlBu_r'
                })

        # Profile plots
        if 'profile' in prompt or '1d' in prompt:
            field = 'Temp'  # Default
            if 'density' in prompt:
                field = 'density'

            vis_config['plots'].append({
                'type': 'profile',
                'field': field,
                'direction': 'x'
            })

        # All timesteps (for movies/comparisons)
        if any(kw in prompt for kw in ['movie', 'animation', 'evolution', 'all timesteps']):
            vis_config['timesteps'] = 'all'

        # If no plots specified, add default temperature
        if not vis_config['plots']:
            vis_config['plots'].append({
                'type': 'slice',
                'field': 'Temp',
                'axis': 'z',
                'colormap': 'hot'
            })

        return vis_config

    def _plan_analysis(self, requirements: dict) -> dict:
        """
        Determine analysis configuration from user requirements.

        Analysis is always enabled (Phase 4 user decision), but can be
        configured based on specific requirements.

        Args:
            requirements: User requirements dict

        Returns
        -------
            Analysis configuration dict
        """
        analysis_config = {
            'enabled': True,  # Always enabled (Phase 4 decision)
            'checks': [
                'cfl',           # CFL violations
                'nan',           # NaN/Inf detection
                'conservation',  # Mass/energy conservation
                'convergence'    # Convergence checks
            ],
            'thresholds': {
                'cfl_max': 1.0,
                'conservation_tol': 1e-6
            },
            'report_format': 'markdown',
            'include_images': False  # Visual diagnostics deferred to Phase 5
        }

        prompt = requirements.get('user_prompt', '').lower()

        # Adjust thresholds based on prompt
        if 'strict' in prompt or 'conservative' in prompt:
            analysis_config['thresholds']['cfl_max'] = 0.8

        # Add performance analysis if requested
        if 'performance' in prompt or 'speed' in prompt:
            analysis_config['checks'].append('performance')

        return analysis_config

    def _llm_fallback_structured(self, query: str, baseline: dict, baseline_case: str) -> dict:
        """
        LLM fallback using instructor with full SimulationPlan model.

        Pre-fills known fields (solver, baseline) and asks LLM to complete
        modifications, reasoning, and confidence scores.

        Args:
            query: User prompt
            baseline: Baseline inputs_content and metadata
            baseline_case: Baseline case path

        Returns
        -------
            Dict compatible with plan_modifications return format, or None if failed
        """
        try:
            import instructor

            from src.services.plan import SimulationPlan
            from src.config import unwrap_llm_client, wrap_llm_client

            # Wrap LLM client with instructor
            base_client = unwrap_llm_client(self.llm_client)
            client = instructor.from_openai(base_client)
            client = wrap_llm_client(client, self.config)

            # Extract solver from baseline metadata
            solver_name = baseline.get('metadata', {}).get('solver')
            if not solver_name:
                raise ValueError("Baseline metadata missing 'solver' field")
            baseline_content = baseline.get('metadata', {}).get('inputs_content', {})
            solver_config = self.code_configs.get(solver_name)

            # Build context for LLM
            baseline_summary = "\n".join([f"  {k}: {v}" for k, v in list(baseline_content.items())[:25]])

            prompt = self._resolve_llm_prompt_template(
                solver_config,
                "structured_fallback_planning",
            ).format(
                query=query,
                baseline_case=baseline_case,
                solver_name=solver_name,
                baseline_summary=baseline_summary,
            )

            logger.info("[LLM] Requesting complete SimulationPlan via structured output...")

            # Get structured SimulationPlan from LLM
            plan = client.chat.completions.create(
                model=self.config.llm_model,
                response_model=SimulationPlan,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_retries=2
            )

            # Override fields we already know (LLM might hallucinate these)
            plan.selected_solver = solver_name
            plan.selected_case = baseline_case
            plan.used_llm = True
            plan.indexing_strategy = 'hierarchical'
            plan.prompt = query
            plan.solver_confidence = 1.0  # Already selected via Level 0
            plan.baseline_confidence = baseline.get('score', 0.8)  # From Level 1

            logger.info(f"[LLM] Generated complete SimulationPlan with {len(plan.modifications)} modifications")
            logger.info(f"[LLM] Confidence: {plan.cbr_confidence:.2f}")
            logger.debug(f"[LLM] Reasoning: {plan.reasoning[:150]}...")

            # Return in plan_modifications format
            return {
                "modifications": plan.modifications,
                "similar_cases": [baseline_case],
                "confidence": plan.cbr_confidence,
                "used_llm": True,
                "reasoning": plan.reasoning,
                "_full_plan": plan  # Include full plan for debugging
            }

        except ImportError:
            logger.warning("[LLM] instructor not installed - falling back to JSON parsing")
            logger.info("[LLM] Install with: pip install instructor")
            return self._llm_fallback_json(query, baseline, baseline_case)

        except Exception as e:
            logger.error(f"[LLM] Structured fallback failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None


# Test
if __name__ == "__main__":
    from amrex_tools import find_inputs_file
    from database.configs.base_amrex_config import BaseAMReXConfig

    logger.debug("\n=== Testing Architect Service ===\n")

    # Offline prompt template smoke test using AMReX Advection_AmrCore inputs.
    amrex_agent_root = Path(__file__).parent.parent.parent
    amrex_root = amrex_agent_root.parent / "amrex"
    if not amrex_root.exists():
        alt_root = amrex_agent_root.parent.parent / "amrex"
        if alt_root.exists():
            amrex_root = alt_root
    exec_dir = amrex_root / "Tests/Amr/Advection_AmrCore/Exec"
    inputs_path = find_inputs_file.invoke({"directory": str(exec_dir)}) if exec_dir.exists() else None
    if inputs_path:
        inputs_text = Path(inputs_path).read_text()
        prompt_templates = BaseAMReXConfig.get_prompt_templates().get("architect", {})
        mod_prompt = prompt_templates["modification_extraction"].format(
            case_description="AMReX Advection_AmrCore test case with a 64x64 grid.",
            inputs_content=inputs_text[:800],
            param_guidance=""
        )
        kb_prompt = prompt_templates["kb_relevance_rating"].format(
            user_prompt="Advection test case on a 64x64 grid.",
            problem_type="advection",
            dimensionality="2D",
            physics="fluid dynamics",
            code_name="AMReX",
            cases_list="\n".join(["1. Advection_AmrCore", "2. Advection_Amr", "3. Advection"])
        )
        baseline_summary = "\n".join(inputs_text.splitlines()[:12])
        fallback_prompt = prompt_templates["structured_fallback_planning"].format(
            query="Advection test case with a 64x64 grid.",
            baseline_case="Tests/Amr/Advection_AmrCore/Exec",
            solver_name="AMReX",
            baseline_summary=baseline_summary
        )
        logger.debug("[Demo] Rendered modification_extraction prompt preview:\n%s", "\n".join(mod_prompt.splitlines()[:12]))
        logger.debug("[Demo] Rendered kb_relevance_rating prompt preview:\n%s", "\n".join(kb_prompt.splitlines()[:12]))
        logger.debug("[Demo] Rendered structured_fallback_planning prompt preview:\n%s", "\n".join(fallback_prompt.splitlines()[:12]))
    else:
        logger.warning("No AMReX Advection_AmrCore inputs found; skipping prompt template demo.")

    logger.debug("[Demo] AMReX-only prompt smoke test complete.")

    logger.debug("\n[OK] Architect service test complete")
