"""
AMReX inputs file management.

Provides config-aware orchestration and file generation services.
"""

import json
import logging
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from amrex_tools import dict_to_pele_inputs, parse_amrex_inputs, validate_amrex_inputs
from database.configs.registry import is_pele_solver

# Keep amrex_agent root on path for dynamic tool imports.
AMREX_AGENT_ROOT = Path(__file__).parent.parent.parent  # From src/services/files.py -> amrex_agent/
if str(AMREX_AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AMREX_AGENT_ROOT))

logger = logging.getLogger(__name__)


def _resolve_pele_validation_tool() -> Any | None:
    """Load Pele validation tool if available (solver-specific)."""
    try:
        module = import_module("utils.pele_tools")
    except Exception as exc:
        logger.debug(f"[DEBUG] Could not import utils.pele_tools: {exc}")
        logger.debug(f"[DEBUG] AMREX_AGENT_ROOT: {AMREX_AGENT_ROOT}")
        logger.debug(f"[DEBUG] utils/pele_tools.py exists: {(AMREX_AGENT_ROOT / 'utils' / 'pele_tools.py').exists()}")
        return None
    return getattr(module, "validate_pele_inputs", None)

class AMReXInputsService:
    """Service for reading/writing AMReX inputs files.

    Core parsing/writing uses amrex_tools utilities.
    Solver-specific validation is routed via the registry when available.

    Example:
        >>> service = AMReXInputsService(config)
        >>> params = service.read("inputs")
        >>> params["amr"]["max_level"] = 3
        >>> service.write("new_inputs", params)
    """

    def __init__(self, config):
        self.config = config

    def read(self, inputs_path: str | Path,
             source_info: dict | None = None) -> dict[str, Any]:
        """
        Parse inputs file using amrex_tools.parse_amrex_inputs.

        Call context: Used by Input Writer and validation workflows.

        Parameters
        ----------
        inputs_path : str or Path
            Path to the inputs file.
        source_info : dict or None, optional
            Optional metadata to store with the parsed inputs.

        Returns
        -------
        dict
            Parsed parameter dictionary.
        """
        inputs_path = Path(inputs_path)

        if not inputs_path.exists():
            raise FileNotFoundError(f"Inputs file not found: {inputs_path}")

        logger.info(f" Reading {inputs_path}")
        params = parse_amrex_inputs(str(inputs_path), source_info)

        n_groups = len(params)
        n_total = sum(len(v) if isinstance(v, dict) else 1 for v in params.values())
        logger.info(f"[ OK ] Parsed {n_groups} groups, {n_total} parameters")

        return params

    def write(self, output_path: str | Path, params: dict[str, Any],
              template_path: Path | None = None) -> None:
        """
        Write parameters using amrex_tools.dict_to_pele_inputs.

        Call context: Used by Input Writer to serialize inputs files.

        Parameters
        ----------
        output_path : str or Path
            Path to write the inputs file.
        params : dict
            Parameter dictionary to serialize.
        template_path : Path or None, optional
            Template file to preserve formatting.

        Returns
        -------
        None
            Writes output to disk.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f" Writing {output_path}")

        # dict_to_pele_inputs signature: (inputs_dict, output_path, base_inputs_dict)
        base_dict = None
        if template_path and template_path.exists():
            base_dict = parse_amrex_inputs(str(template_path))

        dict_to_pele_inputs(params, str(output_path), base_dict)
        logger.info(f"[ OK ] Wrote {output_path}")

    def fetch_example(self, example_name: str,
                      code: str | None = None,
                      save_dir: Path | None = None,
                      force_download: bool = False,
                      version: str = "development") -> dict[str, Any]:
        """
        Fetch example using config-driven catalog.

        Call context: Used by services to pull canonical example inputs.

        Parameters
        ----------
        example_name : str
            Example key from the solver's catalog.
        code : str or None, optional
            Solver name (defaults to config.default_solver).
        save_dir : Path or None, optional
            Directory to save fetched files.
        force_download : bool, optional
            Whether to re-download even if cached.
        version : str, optional
            Version tag for the example.

        Returns
        -------
        dict
            Example metadata with local_path, repo_path, case_dir, and provenance.
        """
        if code is None:
            code = self.config.default_solver
            if not code:
                raise ValueError("No default solver configured for example fetch")

        logger.info(f" Fetching example: {example_name} ({code})")

        code_registry = self.config.get_code_registry()
        config_cls = code_registry.get(code)
        if not config_cls:
            raise ValueError(f"Unknown solver for example fetch: {code}")

        repo_root = self.config.repositories.get(code)
        result = config_cls.fetch_example(
            example_name,
            save_dir=save_dir,
            force_download=force_download,
            version=version,
            repo_root=repo_root,
        )

        if not result:
            logger.error(f"[ERROR] Failed to fetch: {example_name}")
            return {}

        logger.info(f"[ OK ] Fetched: {result.get('local_path', example_name)}")

        # Add case_dir if we have repo path
        if 'repo_path' in result and repo_root:
            repo_rel_path = Path(result['repo_path'])
            case_rel_dir = repo_rel_path.parent

            case_dir = Path(repo_root) / case_rel_dir

            if case_dir.exists():
                result['case_dir'] = str(case_dir)
                result['case_dir_exists'] = True
                logger.info(f" Case directory: {case_dir}")
            else:
                result['case_dir'] = str(case_dir)
                result['case_dir_exists'] = False
                logger.warning(f"[WARN] Case directory not found: {case_dir}")

        return result

    def verify_inputs_match_case(self,
                                 inputs_path: str | Path,
                                 case_dir: str | Path) -> dict[str, Any]:
        """
        Verify inputs file is compatible with case directory.

        Checks:
        - inputs file exists in case_dir or can be used there
        - GNUmakefile exists in case_dir

        Call context: Used by runner preparation to validate inputs placement.

        Parameters
        ----------
        inputs_path : str or Path
            Path to inputs file.
        case_dir : str or Path
            Directory with GNUmakefile.

        Returns
        -------
        dict
            Compatibility report with "compatible" flag and warnings.
        """
        from pathlib import Path

        inputs_path = Path(inputs_path)
        case_dir = Path(case_dir)

        checks = {
            'compatible': True,
            'warnings': []
        }

        # Check 1: Case dir exists
        if not case_dir.exists():
            checks['compatible'] = False
            checks['warnings'].append(f"Case directory not found: {case_dir}")
            return checks

        # Check 2: Has GNUmakefile
        if not (case_dir / 'GNUmakefile').exists():
            checks['compatible'] = False
            checks['warnings'].append(f"No GNUmakefile in {case_dir}")
            return checks

        # Check 3: Inputs file exists
        if not inputs_path.exists():
            checks['compatible'] = False
            checks['warnings'].append(f"Inputs file not found: {inputs_path}")
            return checks

        # Check 4: (Optional) Parse both and compare chemistry, dimensions
        try:
            self.read(inputs_path)

            # Look for probin file in case_dir
            probin_files = list(case_dir.glob("probin*"))
            if probin_files:
                # Could parse and compare chemistry mechanisms
                checks['probin_found'] = str(probin_files[0])

        except Exception as e:
            checks['warnings'].append(f"Could not parse inputs: {e}")

        return checks

    def validate(self, inputs_path: str | Path, solver_name: str | None = None) -> str:
        """
        Validate inputs using solver-specific tools when available.

        Call context: Used by Input Writer and Reviewer validation steps.

        Parameters
        ----------
        inputs_path : str or Path
            Path to the inputs file.
        solver_name : str or None, optional
            Solver name override for selecting the validation tool.

        Returns
        -------
        str
            Validation output as a string.
        """
        inputs_path = Path(inputs_path)

        logger.info(f" Validating {inputs_path}")
        tool = None
        solver_name = solver_name or self.config.default_solver
        if solver_name and is_pele_solver(solver_name):
            tool = _resolve_pele_validation_tool()

        if tool is None:
            logger.info("[WARN] No solver-specific validator available; using generic validation")
            if hasattr(validate_amrex_inputs, "invoke"):
                return validate_amrex_inputs.invoke({"inputs_file": str(inputs_path)})
            return validate_amrex_inputs(str(inputs_path))

        if hasattr(tool, "invoke"):
            report = tool.invoke({"inputs_file": str(inputs_path)})
        else:
            report = tool(str(inputs_path))

        if "ERROR" in report or "error" in report.lower():
            logger.warning("[WARN] Validation found issues")
        else:
            logger.info("[ OK ] Validation passed")

        return report

    def write_full_setup(self, config_json: str, output_dir: str | Path,
                        executable_path: str | None = None,
                        selected_solver: str | None = None,
                        system: str = "perlmutter") -> str:
        """
        Write full simulation using FileGenerationService.

        Call context: Used by higher-level services to materialize a run directory.

        Parameters
        ----------
        config_json : str
            JSON-encoded configuration payload.
        output_dir : str or Path
            Output directory for generated files.
        executable_path : str or None, optional
            Executable path to embed in the submit script.
        selected_solver : str or None, optional
            Solver override.
        system : str, optional
            Target system for resource estimation.

        Returns
        -------
        str
            JSON-encoded mapping of generated files.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        from src.services.file_generation import FileGenerationService

        logger.info(f" Writing simulation files to {output_dir}")
        generator = FileGenerationService(self.config)
        files = generator.write_simulation_files(
            config_json=config_json,
            output_dir=str(output_dir),
            selected_solver=selected_solver,
            executable_path=executable_path,
            system=system,
        )

        logger.info(f"[ OK ] Created simulation in {output_dir}")
        return json.dumps(files, indent=2)

    def extract_key_params(self, params: dict, selected_solver: str | None = None) -> dict[str, Any]:
        """
        Extract commonly modified parameters for LLM manipulation.

        Call context: Used by planning/UX flows to surface key settings.

        Parameters
        ----------
        params : dict
            Parsed parameter dictionary.
        selected_solver : str or None, optional
            Solver name for schema-specific extraction.

        Returns
        -------
        dict
            Extracted key parameters.
        """
        from database.configs import BaseAMReXConfig, discover_code_configs

        registry = {}
        if hasattr(self.config, "get_code_registry"):
            registry = self.config.get_code_registry()
        else:
            registry = {c.code_name: c for c in discover_code_configs()}

        config_cls = None
        if selected_solver:
            config_cls = registry.get(selected_solver)
        if not config_cls:
            lower_registry = {name.lower(): name for name in registry}
            for section in params:
                name = lower_registry.get(str(section).lower())
                if name:
                    config_cls = registry.get(name)
                    break
        if not config_cls:
            config_cls = BaseAMReXConfig

        return config_cls.extract_key_params(params)


# Test
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from amrex_tools import find_inputs_file

    from src.services.config_service import ConfigService

    logger.debug("\n=== Testing AMReX Inputs Service ===\n")

    config = ConfigService().initialize()
    service = AMReXInputsService(config)

    amrex_root = config.amrex_repo_path
    if not amrex_root or not amrex_root.exists():
        amrex_root = None
        for parent in Path(__file__).resolve().parents:
            candidate = parent / "amrex"
            if candidate.exists():
                amrex_root = candidate
                break
    if not amrex_root:
        logger.warning("No AMReX repo found; skipping tests.")
        sys.exit(0)
    exec_dir = amrex_root / "Tests/Amr/Advection_AmrCore/Exec"
    inputs_path = find_inputs_file.invoke({"directory": str(exec_dir)}) if exec_dir.exists() else None
    if not inputs_path:
        logger.warning(f"No AMReX inputs found under {exec_dir}; skipping tests.")
        sys.exit(0)

    filepath = Path(inputs_path)
    logger.debug(f"  Using inputs: {filepath}")

    # Test 1: Read it
    logger.debug("\n[Test 1] Read inputs:")
    params = service.read(filepath)
    logger.debug(f"  Groups: {list(params.keys())[:10]}")

    # Test 2: Extract key params
    logger.debug("\n[Test 2] Extract key parameters:")
    key_params = service.extract_key_params(params)
    for k, v in list(key_params.items())[:8]:
        logger.debug(f"    {k} = {v}")

    # Test 3: Modify and write
    logger.debug("\n[Test 3] Modify and write:")
    params.setdefault("amr", {})["max_level"] = 3
    output = Path("/tmp/test_inputs_modified")
    service.write(output, params)

    # Verify
    verify = service.read(output)
    logger.debug(f"  Modified max_level: {verify.get('amr', {}).get('max_level')}")

    # Test 4: Validate
    logger.debug("\n[Test 4] Validate inputs:")
    try:
        report = service.validate(filepath)
        logger.debug(f"  Report length: {len(report)} chars")
    except TypeError as e:
        logger.warning(f"[WARN] Validation skipped: {e}")

    logger.debug("\n[PASS] Files service ready!")
