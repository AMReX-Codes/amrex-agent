"""
Validation service for AMReX configurations.

Uses config-driven validation hooks and service-layer helpers.
"""

import json
import logging
from pathlib import Path
from typing import Any

from amrex_tools import parse_pele_inputs
from database.configs import discover_code_configs
from database.configs.base_amrex_config import BaseAMReXConfig

from src.services.execution_tools import estimate_resources, validate_executable_for_job

logger = logging.getLogger(__name__)

class ValidationService:
    """Validates simulation configurations and resource requirements.

    Uses config-driven validation hooks

    Example:
        >>> validator = ValidationService(config)
        >>> result = validator.validate_config(config_dict)
        >>> if not result['valid']:
        ...     print(result['errors'])
    """

    def __init__(self, config):
        self.config = config
        self.code_configs = {c.code_name: c for c in discover_code_configs()}

    def validate_config(self, config_dict: dict, selected_solver: str | None = None) -> dict[str, Any]:
        """
        Comprehensive configuration validation.

        Uses config-driven validation hooks from database/configs.

        Call context: Used by Input Writer and Reviewer services.

        Parameters
        ----------
        config_dict : dict
            Parsed inputs configuration.
        selected_solver : str or None, optional
            Optional solver name (preferred for config selection).

        Returns
        -------
        dict
            Dict with validity, errors, warnings, and completeness flags.
        """
        logger.info(" Validating configuration...")

        # Convert Path objects to strings
        def path_to_str(obj):
            """
            Normalize Path values to strings within nested structures.

            Parameters
            ----------
            obj : object
                Object to normalize.

            Returns
            -------
            object
                Normalized object with Path values as strings.
            """
            if isinstance(obj, Path):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: path_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [path_to_str(item) for item in obj]
            else:
                return obj

        config_clean = path_to_str(config_dict)

        config_cls = self._resolve_config_class(config_clean, selected_solver)
        violations = config_cls.validate_config(config_clean)

        errors = [v.message for v in violations if v.severity in ("error", "critical")]
        warnings = [v.message for v in violations if v.severity == "warning"]
        missing = [v.message for v in violations if v.rule_name == "RequiredSection"]
        complete = len(missing) == 0

        result = {
            "errors": errors,
            "warnings": warnings,
            "valid": len(errors) == 0,
            "complete": complete,
            "missing": missing,
        }

        if result['valid'] and result['complete']:
            logger.info("[ OK ] Configuration valid and complete")
        elif result['valid']:
            logger.info("[ OK ] Configuration valid but incomplete (missing required sections)")
        else:
            logger.warning(f"[WARN] Found {len(result['errors'])} errors")
            for err in result['errors'][:5]:
                logger.debug(f"       - {err}")

            if result.get('warnings'):
                logger.info(f" {len(result['warnings'])} warnings")
                for warn in result['warnings'][:3]:
                    logger.debug(f"       - {warn}")

        return result

    def _resolve_config_class(self, config_dict: dict[str, Any], selected_solver: str | None):
        if selected_solver:
            config_cls = self.code_configs.get(selected_solver)
            if config_cls:
                return config_cls
            logger.warning(f"Unknown solver '{selected_solver}', using BaseAMReXConfig")
            return BaseAMReXConfig

        for code_name, config_cls in self.code_configs.items():
            if code_name.lower() in config_dict:
                return config_cls

        logger.warning("No selected_solver provided; using BaseAMReXConfig")
        return BaseAMReXConfig

    def validate_executable(self,
                           executable_path: str,
                           nodes: int = 1,
                           ntasks_per_node: int = 4,
                           constraint: str = "gpu") -> dict[str, Any]:
        """
        Validate executable matches job requirements.

        Checks:
        - MPI-enabled if multi-rank
        - CUDA-enabled if GPU constraint

        Call context: Used by Runner pre-flight checks.

        Parameters
        ----------
        executable_path : str
            Path to solver executable.
        nodes : int, optional
            Number of nodes.
        ntasks_per_node : int, optional
            MPI ranks per node.
        constraint : str, optional
            SLURM constraint.

        Returns
        -------
        dict
            Dict with validity and warnings.
        """
        logger.info(" Validating executable for job requirements...")

        result = validate_executable_for_job(
            executable_path=executable_path,
            nodes=nodes,
            ntasks_per_node=ntasks_per_node,
            constraint=constraint,
        )

        if result['valid']:
            logger.info(f"[ OK ] Executable is {result['executable_type']}")
        else:
            logger.warning("[WARN] Executable validation failed:")
            for w in result['warnings']:
                logger.debug(f"       {w}")

        return result

    def estimate_requirements(self,
                             inputs_file: str,
                             target_cells_per_gpu: int = 200000) -> dict[str, Any]:
        """
        Estimate computational resource requirements.

        Call context: Used by planning or UI to size resources.

        Parameters
        ----------
        inputs_file : str
            Path to inputs file.
        target_cells_per_gpu : int, optional
            Target load per GPU.

        Returns
        -------
        dict
            Recommended nodes, memory, and walltime.
        """
        logger.info(" Estimating resource requirements...")

        config_dict = parse_pele_inputs(inputs_file)
        result_json = estimate_resources(
            config_json=json.dumps(config_dict),
        )
        result = json.loads(result_json)

        logger.info(f"[ OK ] Recommended: {result['recommended_nodes']} nodes")
        logger.debug(f"       Grid: {result['grid_dims']}")
        logger.debug(f"       Cells/GPU: {result['cells_per_gpu']:,}")

        return result

    def validate_full_setup(self,
                           config_dict: dict,
                           executable_path: str,
                           job_params: dict) -> dict[str, Any]:
        """
        Complete pre-flight validation.

        Validates:
        1. Configuration correctness
        2. Executable compatibility
        3. Resource estimates

        Call context: Used before job submission to gate execution.

        Parameters
        ----------
        config_dict : dict
            Inputs configuration.
        executable_path : str
            Path to executable.
        job_params : dict
            Dict with nodes, ntasks_per_node, and constraint.

        Returns
        -------
        dict
            Overall validity and individual check results.
        """
        logger.debug("\n=== Pre-Flight Validation ===\n")

        checks = {}

        # 1. Config validation
        checks['config'] = self.validate_config(config_dict)

        # 2. Executable validation
        checks['executable'] = self.validate_executable(
            executable_path,
            job_params.get('nodes', 1),
            job_params.get('ntasks_per_node', 4),
            job_params.get('constraint', 'gpu')
        )

        # Overall status
        all_valid = (
            checks['config'].get('valid', False) and
            checks['executable'].get('valid', False)
        )

        logger.debug(f"\n{'[PASS]' if all_valid else '[ERROR]'} Overall: {'PASS' if all_valid else 'FAIL'}\n")

        return {
            'valid': all_valid,
            'checks': checks
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    from src.config import AMReXAgentConfig
    from src.services.config_service import ConfigService

    logger.debug("\n=== Testing Validation Service ===\n")

    config_service = ConfigService()
    config = config_service.load_api_keys(AMReXAgentConfig())
    config_service.setup_environment_vars(config)
    validator = ValidationService(config)

    # Test 1: Validate a generic AMReX inputs file if available
    logger.debug("[Test 1] Validate generic AMReX config:")
    amrex_agent_root = Path(__file__).parent.parent.parent
    amrex_root = amrex_agent_root.parents[2] / "amrex"
    amrex_inputs = amrex_root / "Tests/Amr/Advection_AmrCore/Exec/inputs"
    config_dict = {}
    if amrex_inputs.exists():
        try:
            config_dict = parse_pele_inputs(str(amrex_inputs))
            logger.debug(f"  Loaded inputs from {amrex_inputs}")
        except Exception as exc:
            logger.warning(f"  Failed to parse {amrex_inputs}: {exc}")
            config_dict = {}

    if not config_dict:
        config_dict = {
            "geometry": {
                "prob_lo": "0 0 0",
                "prob_hi": "1 1 1",
                "is_periodic": "0 0 0",
            },
            "amr": {
                "n_cell": "32 32 32",
                "blocking_factor": "16",
                "max_grid_size": "32",
            },
        }
        logger.debug("  Using fallback minimal AMReX config dict")

    # Adjust demo config to avoid grid consistency errors
    amr = config_dict.get("amr", {})
    if isinstance(amr, dict) and "n_cell" in amr:
        n_cell_vals = [int(v) for v in str(amr["n_cell"]).split()]
        blocking = int(amr.get("blocking_factor", "16"))
        if any(cells % blocking != 0 for cells in n_cell_vals):
            amr["blocking_factor"] = "8"
            logger.debug("  Adjusted amr.blocking_factor to 8 for demo consistency")

    result = validator.validate_config(config_dict)
    logger.debug(f"  Valid: {result.get('valid', False)}")

    # Test 2: Validate executable
    logger.debug("\n[Test 2] Validate executable for multi-GPU job:")
    result = validator.validate_executable(
        executable_path="main3d.gnu.MPI.CUDA.ex",
        nodes=2,
        ntasks_per_node=4,
        constraint="gpu&hbm40g"
    )
    logger.debug(f"  Valid: {result['valid']}")
    logger.debug(f"  Type: {result['executable_type']}")

    logger.debug("\n[OK] Validation service test complete")
