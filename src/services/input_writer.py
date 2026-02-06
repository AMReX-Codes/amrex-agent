"""
Input writer service - Applies architectural plan to generate configs.

Takes architect's plan (baseline + modifications) and produces final inputs file
Uses the tested pattern from 02_llm_qa_notebook.md
"""

import logging
from pathlib import Path

from amrex_tools import dict_to_pele_inputs, parse_pele_inputs

from src.services.cases import AMReXCasesService
from src.services.config_model_factory import ConfigModelFactory
from src.services.files import AMReXInputsService
from src.services.inputs_file_selector import InputsFileSelector
from src.services.inputs_file_writer import InputsFileWriter

# Input Writer imports (Schema-Based Configuration System)
from src.services.rule_engine import RuleEngine
from src.services.validation import ValidationService

logger = logging.getLogger(__name__)

class InputWriterService:
    """Applies architect's plan to generate final configuration.

    Workflow:
    1. Load baseline inputs
    2. Apply modifications from plan
    3. Validate result
    4. Write inputs file

    Example:
        >>> writer = InputWriterService(config)
        >>> result = writer.apply_plan(architect_plan, output_dir="./run1")
        >>> # result has: config_dict, inputs_path, validation
    """

    def __init__(self, config):
        self.config = config
        self.files_svc = AMReXInputsService(config)
        self.validator = ValidationService(config)
        self.cases_svc = AMReXCasesService(config)

        # Initialize FAISS embedding service for template retrieval
        from .embedding_service_factory import get_embedding_service

        self.embeddings = get_embedding_service(config)

        if self.embeddings.embeddings:
            logger.debug(" [OK] FAISS embeddings initialized for input writer")
        else:
            logger.warning("[WARN] FAISS embeddings not available")
            logger.debug("       Template retrieval will be disabled")


    def _get_build_config(self, code: str) -> dict:
        """
        Get build configuration for code.

        For now, returns permissive default config.
        TODO: Load from actual build configuration.
        """
        return {
            'DIM': '3',
            'USE_EB': 'FALSE',
            'USE_REACTIONS': 'TRUE',
        }

    def _parse_modification_value(self, value: str):
        """
        Parse modification value into appropriate Python type.

        Examples
        --------
            "128 128 128" → [128, 128, 128]
            "0.5" → 0.5
            "true" → True

        Args:
            value: String value from plan

        Returns
        -------
            Parsed Python value
        """
        # Already parsed (from existing code)
        if not isinstance(value, str):
            return value

        # Try list (space-separated)
        if ' ' in value:
            try:
                return [int(v) for v in value.split()]
            except ValueError:
                try:
                    return [float(v) for v in value.split()]
                except ValueError:
                    return value.split()

        # Try number
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                pass

        # Try boolean
        if value.lower() in ['true', 'yes', '1']:
            return True
        if value.lower() in ['false', 'no', '0']:
            return False

        # Return as string
        return value

    def _get_original_baseline_text(self, baseline_spec: dict) -> str:
        """
        Get original baseline text for Ghostwriter pattern.

        For now, returns empty string (scratch generation).
        TODO: Track file path from _load_baseline to enable format preservation.

        Args:
            baseline_spec: Baseline specification

        Returns
        -------
            Original inputs file text, or empty string
        """
        # TODO: Enhance _load_baseline to return file path
        # Then read and return original text here
        return ""


    def apply_plan(self,
                   selected_case: str,
                   modifications: list,
                   baseline: dict[str, str],
                   reasoning: str = "",
                   output_dir: Path | None = None) -> dict:
        """
        Apply execution plan using Input Writer pipeline.

        Integrates Architect Service (Architect) → Input Writer (Writer).
        Implements PRD Amendment C (Load-Modify-Write).
        Reads plan data from Architect via workflow_history (contract line 12-18).

        Pipeline:
            1. LOAD: Baseline → text (using baseline metadata)
            2. HYDRATE: Text → Pydantic model (ConfigModelFactory)
            3. MODIFY: Apply modifications (ConfigModelFactory.apply_modifications)
            4. ENFORCE: Validate and auto-correct (RuleEngine)
            5. SERIALIZE: Model → text with formatting (InputsFileWriter)

        Call context: Primary entry point used by the Input Writer node.

        Parameters
        ----------
        selected_case : str
            Repo-relative case path (e.g., 'Exec/RegTests/PMF').
        modifications : list
            List of (param, value) tuples from Architect.
        baseline : dict
            Baseline metadata with code_name, repo_path, case_path, local_path.
        reasoning : str, optional
            Human-readable explanation for documentation.
        output_dir : Path or None, optional
            Output directory for generated files.

        Returns
        -------
        dict
            Result payload with paths and status.
        """
        logger.debug("[Input Writer] Starting Load-Modify-Write pipeline")

        # Validate inputs per contract line 127-130
        if not baseline or not baseline.get("local_path"):
            raise ValueError(
                f"Incomplete baseline metadata. "
                f"Required: code_name, repo_path, case_path, local_path. "
                f"Got: {baseline}"
            )

        if not selected_case:
            raise ValueError("selected_case cannot be empty")

        if not output_dir:
            raise ValueError("output_dir must be provided")

        # Ensure output directory exists
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Initialize resolution tracking
            unresolved = []
            available_params = []
            remap_count = 0
            inputs_candidates = []
            selected_inputs_path = None
            inputs_file_strategy = getattr(self.config, "inputs_file_strategy", "newest")
            inputs_file_override = getattr(self.config, "inputs_file_override", None)
            inputs_default_precedence = getattr(self.config, "inputs_default_precedence", "default_first")
            effective_strategy = inputs_file_strategy

            # 1. EXTRACT: All parameters already validated and individual
            logger.debug(f"[DEBUG] baseline dict keys: {list(baseline.keys())}")
            logger.debug(f"[DEBUG] baseline dict: {baseline}")
            code_name = baseline.get("code") or baseline.get("code_name")
            if not code_name:
                raise ValueError("Baseline missing 'code' or 'code_name' field")
            baseline_case = selected_case
            logger.debug(f"Plan: solver={code_name}, case={baseline_case}")
            logger.debug(f"Reasoning: {reasoning}")

            # 2. LOAD: Get baseline text using baseline metadata
            # Use baseline.local_path to find the inputs file
            logger.debug(f"[1/5] Loading baseline: {baseline_case}")

            baseline_text = ""
            local_path = Path(baseline.get("local_path", ""))

            # Try to load from local_path first (most direct)
            if local_path.exists():
                # Honor explicit override even if strategy is left at default
                if inputs_file_override:
                    if inputs_file_strategy != "override":
                        logger.warning(
                            "inputs_file_override is set while inputs_file_strategy='%s' (default is 'newest'); "
                            "honoring override anyway.",
                            inputs_file_strategy
                        )
                    override_path = Path(inputs_file_override)
                    if not override_path.is_absolute():
                        override_path = local_path / override_path
                    if override_path.exists() and override_path.is_file():
                        effective_strategy = "override"
                        inputs_file_strategy = effective_strategy
                        selected_inputs_path = str(override_path)
                        inputs_candidates = [override_path]
                        logger.debug(f"Loading baseline from override: {override_path}")
                        baseline_text = override_path.read_text()
                    else:
                        logger.warning(
                            "inputs_file_override did not resolve to a file: %s; "
                            "falling back to strategy '%s'.",
                            override_path,
                            inputs_file_strategy
                        )

                # Only apply defaults/strategy if override didn't already resolve
                if not baseline_text:
                    # Look for inputs file in common locations
                    # Use config-based patterns
                    from database.configs import get_config_for_path
                    config_cls = get_config_for_path(str(local_path))

                    repo_root = None
                    if hasattr(self.config, "repositories"):
                        repo_root = self.config.repositories.get(code_name)
                    default_inputs_path = None
                    if hasattr(config_cls, "resolve_default_inputs_path"):
                        default_inputs_path = config_cls.resolve_default_inputs_path(repo_root)
                    if default_inputs_path:
                        try:
                            default_inputs_path.relative_to(local_path)
                        except ValueError:
                            if inputs_default_precedence == "strategy_first":
                                logger.info(
                                    "Default inputs path is outside selected case directory; "
                                    "strategy_first will ignore it: %s (case: %s)",
                                    default_inputs_path,
                                    local_path
                                )
                            else:
                                logger.warning(
                                    "Default inputs path is outside selected case directory: %s (case: %s)",
                                    default_inputs_path,
                                    local_path
                                )

                    if inputs_default_precedence == "default_first" and default_inputs_path:
                        if default_inputs_path.exists() and default_inputs_path.is_file():
                            effective_strategy = "default"
                            inputs_file_strategy = effective_strategy
                            selected_inputs_path = str(default_inputs_path)
                            inputs_candidates = [default_inputs_path]
                            logger.debug(f"Loading baseline from default inputs: {default_inputs_path}")
                            baseline_text = default_inputs_path.read_text()
                        else:
                            logger.warning(
                                "Default inputs path did not resolve to a file: %s; "
                                "falling back to strategy '%s'.",
                                default_inputs_path,
                                inputs_file_strategy
                            )

                    if not baseline_text:
                        inputs_candidates = config_cls.find_inputs_files(local_path)

                        if inputs_candidates:
                            # Use strategy-based selection from files we found
                            strategy = effective_strategy
                            selected = InputsFileSelector.select_best_inputs_file(
                                local_path,
                                strategy=strategy,
                                excluded_files=[],
                                available_files=inputs_candidates,
                                config=self.config
                            )
                            if selected:
                                selected_inputs_path = str(selected)
                                logger.debug(f"Loading baseline from: {selected} (strategy: {strategy})")
                                baseline_text = selected.read_text()

                    if not baseline_text and inputs_default_precedence == "strategy_first" and default_inputs_path:
                        if default_inputs_path.exists() and default_inputs_path.is_file():
                            effective_strategy = "default"
                            inputs_file_strategy = effective_strategy
                            selected_inputs_path = str(default_inputs_path)
                            inputs_candidates = [default_inputs_path]
                            logger.debug(f"Loading baseline from default inputs: {default_inputs_path}")
                            baseline_text = default_inputs_path.read_text()
                        else:
                            logger.warning(
                                "Default inputs path did not resolve to a file: %s; "
                                "no valid inputs found after strategy selection.",
                                default_inputs_path
                            )

            # Fallback: Use cases_service to fetch baseline
            if not baseline_text and hasattr(self, 'cases_svc') and self.cases_svc:
                try:
                    logger.debug("Attempting cases_service fallback")
                    case_result = self.cases_svc.get_case_files(baseline_case)
                    baseline_text = case_result.get('inputs_text', '')
                except Exception as e:
                    logger.debug(f"cases_service fallback failed: {e}")

            if not baseline_text:
                logger.warning(f"Empty baseline for {baseline_case} at {local_path}")
                baseline_text = "# Empty baseline\n"

            if not modifications and baseline_text and selected_inputs_path:
                logger.info("[2/5] Skipping model hydration (no modifications)")
                inputs_path = output_dir / "inputs"
                inputs_path.write_text(baseline_text)
                logger.info(f"Wrote {len(baseline_text)} bytes to {inputs_path}")

                if hasattr(self, "_copy_auxiliary_files"):
                    logger.debug("Copying auxiliary files...")
                    baseline_info = {"path": baseline_case, "code": code_name}
                    self._copy_auxiliary_files(baseline_info, output_dir)

                return {
                    "inputs_path": str(inputs_path),
                    "output_dir": str(output_dir),
                    "run_dir": str(output_dir),
                    "modifications_applied": 0,
                    "inputs_file_selected": selected_inputs_path,
                    "inputs_file_strategy": inputs_file_strategy,
                    "inputs_file_override": inputs_file_override,
                    "inputs_candidates": [str(p) for p in inputs_candidates],
                    "solver": code_name,
                    "status": "success",
                    "requires_parameter_resolution": False,
                }

            # 3. HYDRATE: Create Pydantic model from text (Input Writer: Config Model Factory)
            logger.debug(f"[2/5] Creating Pydantic model for {code_name}")

            # Get build config
            build_config = self._get_build_config(code_name)

            # Load the full schema from database (FIX: was passing empty schema dict)
            try:
                schema_dir = self.config.amrex_agent_root / "database/schemas"
                if hasattr(self.config, "get_code_registry"):
                    code_registry = self.config.get_code_registry()
                else:
                    from database.configs import discover_code_configs
                    code_registry = {c.code_name: c for c in discover_code_configs()}

                from database.configs.base_amrex_config import BaseAMReXConfig
                solver_config = code_registry.get(code_name, BaseAMReXConfig)

                repo_path = None
                if hasattr(self.config, "repositories"):
                    repo_path = self.config.repositories.get(code_name)
                if not repo_path:
                    repo_path = baseline.get("repo_path") or baseline.get("local_path")
                repo_path = Path(repo_path) if repo_path else self.config.amrex_agent_root

                schema_path = ConfigModelFactory.resolve_schema_path(
                    solver_config,
                    schema_dir,
                    repo_path,
                )
                logger.debug(f"Loading schema from: {schema_path}")

                raw_schema = ConfigModelFactory.load_schema(schema_path)

                # Extract 'parameters' section if present, otherwise use entire schema
                if isinstance(raw_schema, dict) and 'parameters' in raw_schema:
                    schema = raw_schema['parameters']
                    logger.debug(f"Loaded schema with {len(schema)} parameters from {schema_path.name}")
                else:
                    schema = raw_schema
                    logger.debug(f"Loaded schema with {len(schema)} entries from {schema_path.name}")

            except Exception as e:
                logger.error(f"Failed to load schema: {e}")
                logger.warning("Falling back to empty schema - modifications may fail")
                schema = {}

            # Create model class from schema
            try:
                model_class = ConfigModelFactory.create_from_schema(
                    schema=schema,  # Now using full schema loaded from database
                    build_config=build_config
                )
                logger.debug(f"Created Pydantic model with {len(schema)} fields")
            except Exception as e:
                logger.error(f"Could not create model class: {e}")
                raise

            # Hydrate model from baseline text
            try:
                config_model = ConfigModelFactory.hydrate(model_class, baseline_text)
                logger.debug("Hydrated model from baseline")
            except Exception as e:
                logger.error(f"Could not hydrate model: {e}")
                raise

            # 4. MODIFY: Apply modifications (Input Writer: Config Model Factory extension)
            logger.debug(f"[InputWriter] Step 3/5: Applying {len(modifications)} modification(s)")
            logger.debug(f"[InputWriter] Modifications to apply: {modifications}")

            baseline_params = [
                line.split('=')[0].strip()
                for line in baseline_text.splitlines()
                if '=' in line and not line.strip().startswith('#')
            ]

            modification_result = ConfigModelFactory.apply_modifications(
                config_model,
                modifications,
                config_service=self.config,
                baseline_params=baseline_params,
                return_details=True,
            )

            # Extract results from new dict return
            config_model = modification_result["config"]
            unresolved = modification_result["unresolved_parameters"]
            available_params = modification_result["available_schema_params"]
            remap_count = modification_result["remap_success_count"]
            remap_mapping = modification_result.get("remap_mapping", {})
            applied_params = set(modification_result.get("applied_params", []))

            logger.debug("[DATA TRANSFER] Received result from ConfigModelFactory")
            logger.debug(f"[DATA TRANSFER] Result keys: {list(modification_result.keys())}")
            logger.debug(f"[DATA TRANSFER]   - unresolved_parameters: {len(unresolved)}")
            logger.debug(f"[DATA TRANSFER]   - available_schema_params: {len(available_params)}")
            logger.debug(f"[DATA TRANSFER]   - remap_success_count: {remap_count}")

            # Check if we have unresolved parameters that need architect attention
            if unresolved:
                logger.warning(
                    f"[InputWriter] {len(unresolved)} unresolved parameters "
                    f"(remap fixed {remap_count}): {[p[0] for p in unresolved]}"
                )

            logger.debug("[InputWriter] Applied modifications completed")

            # 5. ENFORCE: Validate and auto-correct (Input Writer: Rule Engine Orchestrator)
            # SKIP for 0 modifications
            if modifications:
                logger.debug("[InputWriter] Step 4/5: Validating with RuleEngine")
                code_registry = {}
                if hasattr(self.config, "get_code_registry"):
                    code_registry = self.config.get_code_registry()
                else:
                    from database.configs import discover_code_configs
                    code_registry = {c.code_name: c for c in discover_code_configs()}

                from database.configs.base_amrex_config import BaseAMReXConfig
                solver_config = code_registry.get(code_name, BaseAMReXConfig)
                config_model = RuleEngine.enforce(
                    config_model,
                    solver_config,
                    build_config=build_config
                )
            else:
                logger.debug("[InputWriter] Step 4/5: Skipping RuleEngine (0 modifications)")

            # 6. SERIALIZE: Write output (Input Writer: Inputs File Writer)
            logger.debug("[5/5] Serializing to inputs file")

            serialize_kwargs = {
                "original_text": baseline_text,  # Preserve formatting
            }
            if applied_params:
                serialize_kwargs["modified_keys"] = applied_params

            output_text = InputsFileWriter.serialize(
                config_model,
                **serialize_kwargs
            )

            # Write to file
            inputs_path = output_dir / "inputs"
            inputs_path.write_text(output_text)
            logger.debug(f"Wrote {len(output_text)} bytes to {inputs_path}")

            # Copy auxiliary files if method exists
            if hasattr(self, '_copy_auxiliary_files'):
                logger.debug("Copying auxiliary files...")
                # Extract baseline info for auxiliary files
                baseline_info = {'path': baseline_case, 'code': code_name}
                self._copy_auxiliary_files(baseline_info, output_dir)

            logger.debug("[Input Writer] Pipeline complete")

            result = {
                'inputs_path': str(inputs_path),
                'output_dir': str(output_dir),
                'run_dir': str(output_dir),
                'modifications_applied': len(modifications),
                'inputs_file_selected': selected_inputs_path,
                'inputs_file_strategy': inputs_file_strategy,
                'inputs_file_override': inputs_file_override,
                'inputs_candidates': [str(p) for p in inputs_candidates],
                'solver': code_name,
                'status': 'success'
            }

            # Add resolution feedback if there were unresolved parameters
            if unresolved:
                result['requires_parameter_resolution'] = True
                logger.debug("[DATA TRANSFER] Adding resolution feedback to result")
                logger.debug(f"[DATA TRANSFER]   - unresolved_parameters: {len(unresolved)}")
                logger.debug(f"[DATA TRANSFER]   - available_schema_params: {len(available_params)}")
                feedback = ConfigModelFactory.build_parameter_resolution_feedback(
                    unresolved_params=unresolved,
                    config_service=self.config,
                    solver_config=solver_config,
                    config_model=config_model,
                    remap_mapping=remap_mapping,
                    available_schema_params=available_params
                )
                result['unresolved_parameters'] = feedback["unresolved_parameters"]
                result['available_schema_params'] = feedback["available_schema_params"]
                result['suggested_params'] = feedback["suggested_params"]
                result['remap_mapping'] = feedback.get("remap_mapping", {})
                result['resolution_guidance'] = feedback["resolution_guidance"]
            else:
                result['requires_parameter_resolution'] = False

            return result

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            import traceback
            traceback.print_exc()

            # Return error status (don't crash)
            return {
                'inputs_path': None,
                'output_dir': str(output_dir),
                'run_dir': str(output_dir),  # Alias for node compatibility
                'status': 'error',
                'error': str(e)
            }


    def _apply_plan_legacy(self, plan: dict, output_dir: Path) -> dict:
        """
        Fallback to old dictionary-based approach.

        This preserves existing functionality if Input Writer fails.
        TODO: Remove once Input Writer is stable.
        """
        logger.warning("Using fallback mode - Input Writer pipeline failed")

        # Keep old implementation as safety net
        modified_config = self._load_baseline(plan.get('baseline', {}))

        # Apply modifications - convert tuples to dict format if needed
        modifications = plan.get('modifications', [])
        for mod in modifications:
            if isinstance(mod, tuple):
                param, value = mod
                modified_config[param] = value
            elif isinstance(mod, dict):
                param = mod.get('parameter')
                value = mod.get('value')
                if param:
                    modified_config[param] = value

        # Write simple text file
        inputs_path = output_dir / "inputs"
        with open(inputs_path, 'w') as f:
            for key, value in modified_config.items():
                f.write(f"{key} = {value}\n")

        return {
            'inputs_path': str(inputs_path),
            'status': 'fallback'
        }


    def _load_baseline(self, baseline_info: dict) -> dict:
        """Load baseline - auto-clone if needed."""
        # Handle both old ('code_name', 'case_name') and new ('code', 'path') formats
        if 'code_name' in baseline_info:
            # Old format from legacy code
            code = baseline_info['code_name']
            case = baseline_info['case_name']
        elif 'code' in baseline_info:
            # New format from _select_baseline
            code = baseline_info['code']
            case = baseline_info['path']  # Use 'path', not 'name' (which includes code prefix)
        else:
            raise ValueError("Baseline info missing 'code' and 'path' fields")

        logger.debug(f"       Baseline: {code}/{case}")

        # Ensure code is available (will clone if needed)
        code_path = self.cases_svc.ensure_code_available(code)

        if not code_path:
            raise ValueError(f"Could not locate or clone repository for {code}")

        # Now find inputs in code_path
        case_simple = case.split('/')[-1]

        # Try full path first
        if 'Exec' in case:
            case_dir = Path(code_path) / case
        else:
            case_dir = Path(code_path) / 'Exec' / 'RegTests' / case_simple

        if case_dir.exists():
            # Find inputs
            # Use strategy-based selection
            strategy = getattr(self.config, 'inputs_file_strategy', 'newest')
            # Note: excluded files handled at node level, not here
            selected = InputsFileSelector.select_best_inputs_file(
                case_dir, strategy=strategy, excluded_files=[], config=self.config
            )
            if selected:
                logger.debug(f"       Loading: {selected} (strategy: {strategy})")
                return parse_pele_inputs(str(selected))

        raise FileNotFoundError(
            f"Baseline case not found for code '{code}' at '{case_dir}'. "
            "Ensure the repository is available locally and the case path is correct."
        )

    def _retrieve_similar_templates(self, plan: dict) -> list | None:
        """
        Retrieve similar input file templates from FAISS.

        Uses the prompt and requirements to find cases with similar
        input file patterns. These can serve as references for modifications.

        Args:
            plan: Architect's plan with prompt and requirements

        Returns
        -------
            List of similar template dicts with metadata, or None if FAISS unavailable
        """
        if not self.embeddings or not self.embeddings.indices_available():
            return None

        try:
            # Build search query from plan
            user_prompt = plan.get('prompt', '')
            requirements = plan.get('requirements', {})

            # Enhance query with requirements
            query_parts = [user_prompt]

            if requirements.get('fuel'):
                query_parts.append(f"fuel: {requirements['fuel']}")
            if requirements.get('mechanism'):
                query_parts.append(f"mechanism: {requirements['mechanism']}")
            if requirements.get('grid'):
                grid = requirements['grid']
                # Convert list to space-separated string
                grid_str = ' '.join(map(str, grid)) if isinstance(grid, list) else str(grid)
            query_parts.append(f"grid: {grid_str}")

            search_query = ' '.join(query_parts)

            # Determine code
            code = plan.get('baseline', {}).get('code')
            if not code:
                raise ValueError("Plan baseline missing 'code' field for template search")
            code_lower = code.lower()

            # Query input templates index
            templates_index = f"{code_lower}_input_templates"

            results = self.embeddings.retrieve_faiss(
                templates_index,
                search_query,
                topk=50
            )

            if results.get('results'):
                templates = []
                for result in results['results']:
                    metadata = result.get('metadata', {})
                    templates.append({
                        'case_name': metadata.get('case_name', 'Unknown'),
                        'case_path': metadata.get('case_path', ''),
                        'mechanism': metadata.get('mechanism', ''),
                        'fuel': metadata.get('fuel', ''),
                        'similarity': result.get('score', 0.0),
                        'content_preview': result.get('content', '')[:200]
                    })

                return templates

        except Exception as e:
            logger.debug(f"[DEBUG] FAISS template retrieval failed: {e}")

        return None

    def get_template_suggestions(self, plan: dict) -> str:
        """
        Get human-readable template suggestions for user reference.

        Useful for displaying similar cases that the user might want to review.

        Call context: Used by UI/reporting to show similar template hints.

        Parameters
        ----------
        plan : dict
            Architect's plan.

        Returns
        -------
        str
            Formatted template suggestions, or empty string.
        """
        templates = self._retrieve_similar_templates(plan)

        if not templates:
            return ""

        suggestions = ["Similar input file patterns found:"]
        for i, tmpl in enumerate(templates, 1):
            suggestions.append(f"\n{i}. {tmpl['case_name']}")
            if tmpl['mechanism']:
                suggestions.append(f"   Mechanism: {tmpl['mechanism']}")
            if tmpl['fuel']:
                suggestions.append(f"   Fuel: {tmpl['fuel']}")
            suggestions.append(f"   Similarity: {1.0 - tmpl['similarity']:.2f}")

        return '\n'.join(suggestions)

    def _apply_modifications(self,
                            config: dict,
                            modifications: list) -> list:
        """
        Apply modifications to config (in-place).

        Follows pattern from 02_llm_qa_notebook.md:
        - Deep copy already done by caller
        - Parse parameter path (e.g., "amr.n_cell")
        - Set new value

        Returns
        -------
            List of successfully applied modifications
        """
        applied = []

        for mod in modifications:
            param = mod['parameter']
            new_value = mod['new_value']

            # Parse section.param format
            if '.' in param:
                section, param_name = param.split('.', 1)
            else:
                # Top-level parameter (no section)
                section = ''
                param_name = param

            # Ensure section exists
            if section not in config:
                config[section] = {}

            # Store old value for reporting
            old_value = config[section].get(param_name)

            # Apply new value
            config[section][param_name] = str(new_value)

            applied.append({
                'parameter': param,
                'old_value': old_value,
                'new_value': new_value,
                'reason': mod.get('reason', '')
            })

            logger.debug(f"       {param}: {old_value} → {new_value}")

        return applied

    def _extract_modifications(self,
                              baseline: dict,
                              modified: dict) -> dict:
        """
        Extract only changed parameters.

        This creates the modifications_only dict for dict_to_pele_inputs
        which will comment out base values and show mods at end.
        """
        modifications_only = {}

        for section in modified:
            if section in baseline and isinstance(modified[section], dict):
                modifications_only[section] = {}

                for param, val in modified[section].items():
                    # Include if changed OR new
                    if param not in baseline[section] or baseline[section][param] != val:
                        modifications_only[section][param] = val

        return modifications_only

    def _write_inputs(self,
                     modifications: dict,
                     baseline: dict,
                     output_path: Path) -> Path:
        """
        Write inputs file using tested pattern.

        Uses dict_to_pele_inputs which:
        - Comments baseline params if overridden
        - Puts modifications at end (these are used)
        """
        output_file = dict_to_pele_inputs(
            modifications,              # Modifications only
            str(output_path),          # Output file
            base_inputs_dict=baseline  # Base (will be commented)
        )

        return Path(output_file)

    def _setup_grid(self, plan: dict) -> dict:
        """
        Generate grid configuration from plan requirements.

        Extracts or infers grid parameters from the plan to ensure
        complete grid initialization in the inputs file.

        Args:
            plan: Architect's plan with requirements

        Returns
        -------
            Dict with grid configuration (amr.n_cell, geometry.prob_lo/hi, etc.)

        Example:
            >>> grid = self._setup_grid(plan)
            >>> # grid = {'n_cell': '128 128 128', 'prob_lo': '0 0 0', ...}
        """
        grid_config = {}

        # Determine dimensions from plan
        dimensions = plan.get('requirements', {}).get('dimensions', 3)

        # Determine resolution from plan or defaults
        if 'grid_resolution' in plan:
            # Wherever n_cell is being set
            n_cell = plan['grid_resolution']
            logger.debug(f"[DEBUG] Setting n_cell to: {n_cell!r} (type: {type(n_cell)})")
            grid_res=n_cell
            if isinstance(grid_res, list):
                n_cell = ' '.join(str(x) for x in grid_res)
            else:
                n_cell = str(grid_res)
        elif 'requirements' in plan and 'grid' in plan['requirements']:
            # Try to extract from requirements
            grid_req = plan['requirements']['grid']
            logger.debug(f"[DEBUG] grid from requirements: {grid_req!r} (type: {type(grid_req)})")

            if isinstance(grid_req, list):
                # Convert list [128, 128] → "128 128"
                n_cell = ' '.join(str(x) for x in grid_req)
            elif isinstance(grid_req, str) and 'x' in grid_req:
                # Parse "256x256" → "256 256"
                n_cell = grid_req.replace('x', ' ')
            else:
                logger.debug("[DEBUG] fallback for n_cell")
                n_cell = str(grid_req)

            logger.debug(f"[DEBUG] Converted to n_cell: {n_cell!r}")
        elif plan.get('use_amr', False):
            # Coarse base grid for AMR
            n_cell = "64 64" if dimensions == 2 else "64 64 64"
        else:
            # Fine uniform grid
            n_cell = "128 128" if dimensions == 2 else "128 128 128"

        grid_config['n_cell'] = n_cell

        # Domain bounds (default to unit cube/square)
        if dimensions == 2:
            grid_config['prob_lo'] = "0.0 0.0"
            grid_config['prob_hi'] = "1.0 1.0"
        else:
            grid_config['prob_lo'] = "0.0 0.0 0.0"
            grid_config['prob_hi'] = "1.0 1.0 1.0"

        # AMR levels if specified
        if plan.get('use_amr', False) or plan.get('requirements', {}).get('amr_levels'):
            amr_levels = plan.get('requirements', {}).get('amr_levels', 1)
            grid_config['max_level'] = str(amr_levels)

            # Refinement ratios (default to 2x refinement)
            ref_ratios = ' '.join(['2'] * (amr_levels + 1))
            grid_config['ref_ratio'] = ref_ratios

        return grid_config

    def _add_complete_setup(self, inputs_dict: dict, plan: dict) -> dict:
        """
        Add all sections needed for complete simulation setup.

        Ensures the generated inputs file has everything needed to run:
        - Grid initialization (amr.n_cell, geometry bounds)
        - Domain decomposition (blocking_factor, max_grid_size)
        - I/O settings (plotfiles, checkpoints)
        - Performance tuning (tiling)
        - Physics file paths (chemistry mechanisms)
        - Boundary conditions (if specified)

        This addresses the "input completeness" gap identified in Phase 3.

        Args:
            inputs_dict: Current inputs dictionary
            plan: Architect's plan with requirements

        Returns
        -------
            Enhanced inputs dictionary with complete setup

        Example:
            >>> complete = self._add_complete_setup(inputs_dict, plan)
            >>> # complete now has amr.n_cell, geometry.prob_*, I/O settings, etc.
        """
        # Get requirements from plan
        requirements = plan.get('requirements', {})
        baseline = plan.get('baseline', {})
        code = baseline.get('code_name') or baseline.get('code')
        if not code:
            raise ValueError("Baseline missing 'code_name' or 'code' field")

        # ====================================================================
        # 1. Grid Initialization
        # ====================================================================
        grid_config = self._setup_grid(plan)

        # Add to geometry section
        inputs_dict.setdefault('geometry', {})
        for key, val in grid_config.items():
            if key.startswith('prob_'):
                inputs_dict['geometry'][key] = val

        # Add to amr section
        inputs_dict.setdefault('amr', {})
        for key, val in grid_config.items():
            if key in ['n_cell', 'max_level', 'ref_ratio']:
                inputs_dict['amr'][key] = val

        # ====================================================================
        # 2. Domain Decomposition (MPI parallelization)
        # ====================================================================
        if 'blocking_factor' not in inputs_dict['amr']:
            # Default blocking factor (must divide grid evenly)
            inputs_dict['amr']['blocking_factor'] = str(requirements.get('blocking_factor', 16))

        if 'max_grid_size' not in inputs_dict['amr']:
            # Default max grid size (affects load balancing)
            inputs_dict['amr']['max_grid_size'] = str(requirements.get('max_grid_size', 64))

        # ====================================================================
        # 3. I/O Settings (Plotfiles and Checkpoints)
        # ====================================================================
        inputs_dict['amr'].setdefault('plot_file', 'plt')
        inputs_dict['amr'].setdefault('plot_int', '-1')  # -1 = disabled, or set from requirements
        inputs_dict['amr'].setdefault('checkpoint_files_output', '1')

        # If user specified output frequency
        if 'plot_interval' in requirements:
            inputs_dict['amr']['plot_int'] = str(requirements['plot_interval'])

        if 'checkpoint_interval' in requirements:
            inputs_dict['amr']['check_int'] = str(requirements['checkpoint_interval'])

        # ====================================================================
        # 4. Performance Tuning
        # ====================================================================
        inputs_dict.setdefault('fabarray', {})
        if 'mfiter_tile_size' not in inputs_dict['fabarray']:
            # Tiling for better cache performance
            dimensions = requirements.get('dimensions', 3)
            if dimensions == 2:
                inputs_dict['fabarray']['mfiter_tile_size'] = '1024000 8'
            else:
                inputs_dict['fabarray']['mfiter_tile_size'] = '1024000 8 8'

        # ====================================================================
        # 5. Physics File Paths (Chemistry mechanisms for combustion codes)
        # ====================================================================
        # Check if this code supports chemistry
        code_registry = self.config.get_code_registry()
        solver_config = code_registry.get(code)
        supports_chemistry = solver_config and hasattr(solver_config, 'supports_chemistry') and solver_config.supports_chemistry

        if supports_chemistry and requirements.get('use_reactions', True):
            code_section = code.lower()
            inputs_dict.setdefault(code_section, {})

            # Chemistry mechanism file
            chem_keys = []
            for key in getattr(solver_config, "chemistry_param_keys", []):
                if "." in key:
                    prefix, suffix = key.split(".", 1)
                    if prefix == code_section:
                        chem_keys.append(suffix)
                    else:
                        chem_keys.append(key)
                else:
                    chem_keys.append(key)

            chem_file_key = chem_keys[0] if chem_keys else "chem_file"

            if 'chemistry_mechanism' in requirements and chem_file_key not in inputs_dict[code_section]:
                mechanism = requirements['chemistry_mechanism']
                # Use environment variable for portability
                inputs_dict[code_section][chem_file_key] = (
                    f'${{PELE_PHYSICS_HOME}}/Mechanisms/{mechanism}/chem.bin'
                )

        # ====================================================================
        # 6. Boundary Conditions (if specified in requirements)
        # ====================================================================
        if 'boundary_conditions' in requirements:
            bc = requirements['boundary_conditions']

            # Geometry BC types
            inputs_dict['geometry'].setdefault('is_periodic', bc.get('is_periodic', '0 0 0'))

            # Low-side BCs
            if 'lo_bc' in bc:
                lo_bc = bc['lo_bc']
                inputs_dict['geometry']['lo_bc'] = ' '.join(map(str, lo_bc)) if isinstance(lo_bc, list) else str(lo_bc)

            # High-side BCs
            if 'hi_bc' in bc:
                hi_bc = bc['hi_bc']
                inputs_dict['geometry']['hi_bc'] = ' '.join(map(str, hi_bc)) if isinstance(hi_bc, list) else str(hi_bc)

        # ====================================================================
        # 7. Runtime Settings
        # ====================================================================
        inputs_dict.setdefault('amrex', {})

        # Verbosity (useful for debugging)
        if 'verbose' not in inputs_dict['amrex']:
            inputs_dict['amrex']['verbose'] = '1'

        # FPE trapping (useful for debugging NaNs)
        if 'fpe_trap_invalid' not in inputs_dict['amrex']:
            inputs_dict['amrex']['fpe_trap_invalid'] = '1'

        return inputs_dict


# Test
if __name__ == "__main__":
    from src.config import load_config
    from src.services.architect import ArchitectService

    logger.debug("\n=== Testing Input Writer Service ===\n")

    config = load_config()

    # Create a plan using architect
    logger.debug("[1] Create plan with architect:")
    architect = ArchitectService(config)
    plan = architect.create_plan(
        "2D hydrogen flame, 256x256 grid, AMR 1 level, run 500 steps"
    )

    # Apply plan with writer
    logger.debug("\n[2] Apply plan with writer:")
    writer = InputWriterService(config)
    result = writer.apply_plan(
        plan,
        output_dir="/tmp/test_writer",
        validate=True
    )

    logger.debug("\n[OK] Writer test complete:")
    logger.debug(f"  Inputs: {result['inputs_path']}")
    logger.debug(f"  Applied: {len(result['modifications_applied'])} changes")
    logger.debug(f"  Valid: {result['validation']['valid']}")

    # Show generated file
    logger.debug("\n[3] Generated file preview (first 40 lines):")
    logger.debug("-" * 60)
    inputs_text = Path(result['inputs_path']).read_text()
    preview_lines = inputs_text.split('\n')[:40]
    print('\n'.join(preview_lines))
    if len(inputs_text.split('\n')) > 40:
        logger.debug("...")
