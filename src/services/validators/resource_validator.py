"""
Reviewer Service: Resource Validator: External Resource Validator (DEFERRED).

NOTE: Most functionality deferred to Runner Node (Runner).
This stub validates only critical plan-time dependencies.

Scope:
- Check chemistry files exist in source locations
- Check geometry files (STL/PLY) exist
- Warn on extreme memory estimates

Deferred to Runner Node:
- Disk quota checks
- Run directory permissions
- Detailed SLURM constraints
- Executable compilation
"""
import logging
from pathlib import Path
from typing import Any

from database.configs.registry import (
    build_chemistry_search_paths,
    get_chemistry_param_keys,
)

from src.config import AMReXAgentConfig
from src.services.rules.base import RuleViolation

logger = logging.getLogger(__name__)


class ResourceValidator:
    """
    Reviewer Service: Resource Validator: Validates external runtime resources (minimal).

    Architecture:
    - __init__: Takes AMReXAgentConfig
    - validate: Takes plan dict, checks source file existence
    """

    def __init__(self, config: AMReXAgentConfig):
        """Initialize validator with app config."""
        self.config = config

    @staticmethod
    def check_modifications(modifications: dict[str, str]) -> list[str]:
        """
        Return human-readable warnings for user-edited parameters.
        """
        if not modifications:
            return []
        return ["Resource impact may require additional capacity."]

    def validate(self, plan: dict[str, Any]) -> list[RuleViolation]:
        """
        Validate external resource dependencies.

        Call context: Used by Reviewer to catch missing resource files.

        Parameters
        ----------
        plan : dict
            Execution plan with modifications.

        Returns
        -------
        list of RuleViolation
            Violations (mostly deferred to Runner Node).
        """
        violations = []

        # Extract modifications
        modifications = plan.get('modifications', [])
        if isinstance(modifications, dict):
            modifications = list(modifications.items())

        mods_dict = dict(modifications)

        # Check chemistry files (critical for do_react=1)
        solver_name = plan.get('selected_solver') or plan.get('baseline', {}).get('code')
        self._check_chemistry_files(mods_dict, violations, solver_name)

        # Check geometry files (critical for EB)
        self._check_geometry_files(mods_dict, violations)

        # Warn on extreme memory usage
        self._check_memory_estimate(mods_dict, violations)

        return violations

    def _check_chemistry_files(
        self,
        mods: dict[str, Any],
        violations: list[RuleViolation],
        solver_name: str | None
    ) -> None:
        """
        Check if chemistry mechanism file exists.

        NOTE: Searches CWD → repository root → PelePhysics/Mechanisms.

        Chemistry files are typically mechanism.yaml in subdirectories,
        e.g., drm19/mechanism.yaml, grimech30/mechanism.yaml

        """
        chem_param_keys = get_chemistry_param_keys(solver_name)
        chem_param_name = next((key for key in chem_param_keys if key in mods), None)
        if not chem_param_name:
            return

        chem_file = mods.get(chem_param_name)
        if not chem_file:
            return

        # Search paths
        # Chemistry files can be:
        # 1. Direct path to mechanism.yaml
        # 2. Mechanism name (e.g., "drm19") → resolve to drm19/mechanism.yaml
        repo_paths = []
        if solver_name:
            repo_path = self.config.repositories.get(solver_name)
            if repo_path:
                repo_paths.append(repo_path)
        else:
            repo_paths = list(self.config.repositories.values())

        search_paths = build_chemistry_search_paths(chem_file, repo_paths)

        if not any(p.exists() for p in search_paths):
            violations.append(RuleViolation(
                rule_name="ExternalResource",
                severity="critical",
                parameter=chem_param_name,
                message=f"Chemistry file '{chem_file}' not found in search paths.",
                suggested_fix="Ensure file exists in CWD, NSL database, or configured repository mechanisms."
            ))

    def _check_geometry_files(
        self,
        mods: dict[str, Any],
        violations: list[RuleViolation]
    ) -> None:
        """Check if EB geometry files exist."""
        geom_type = mods.get('eb2.geom_type', '').lower()
        if geom_type not in ['stl', 'ply']:
            return

        geom_file = mods.get('eb2.geom_file')
        if not geom_file:
            return

        # Check if file exists (absolute or relative to CWD)
        path = Path(geom_file)
        if not path.exists() and not (Path.cwd() / geom_file).exists():
            violations.append(RuleViolation(
                rule_name="ExternalResource",
                severity="critical",
                parameter="eb2.geom_file",
                message=f"Geometry file '{geom_file}' not found.",
                suggested_fix="Ensure STL/PLY file exists in current directory or provide absolute path."
            ))

    def _check_memory_estimate(
        self,
        mods: dict[str, Any],
        violations: list[RuleViolation]
    ) -> None:
        """Warn on extreme memory usage (heuristic)."""
        n_cell = mods.get('amr.n_cell')
        if not n_cell:
            return

        try:
            # Parse grid dimensions
            if isinstance(n_cell, str):
                dims = [int(x) for x in n_cell.split()]
            elif isinstance(n_cell, list):
                dims = n_cell
            else:
                return

            # Calculate total cells
            total_cells = 1
            for d in dims:
                total_cells *= d

            # Heuristic: 50 vars per cell, 8 bytes, 1.5x overhead
            n_vars = 50
            bytes_per_cell = n_vars * 8 * 1.5
            est_memory_gb = (total_cells * bytes_per_cell) / (1024**3)

            # Warn if > 1TB (extreme)
            if est_memory_gb > 1000:
                violations.append(RuleViolation(
                    rule_name="ResourceLimit",
                    severity="warning",
                    parameter="amr.n_cell",
                    message=f"Estimated memory ~{est_memory_gb:.0f} GB exceeds typical node limits.",
                    suggested_fix="Consider reducing grid size or using distributed runs."
                ))
        except (ValueError, TypeError, IndexError):
            # Cannot parse, skip check
            pass
