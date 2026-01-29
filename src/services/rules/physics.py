"""
Reviewer Service: Physics Validator: Physics Consistency Rules.

Domain-specific physics validation (Tier 1 Critical Parameters).
Extends Input Writer: Rule Factory RuleEngine with solver-specific constraints.
"""
from database.configs.registry import (
    get_cfl_model_aliases,
    get_explicit_cfl_param_name,
)
from pydantic import BaseModel

from .base import RuleViolation, ValidationRule


class CFLStabilityRule(ValidationRule):
    """
    Enforce CFL condition for explicit time integration.

    Physics: Explicit codes require CFL ≤ 1.0 for numerical stability.
    Scope: Explicit solvers only (not implicit/low-Mach).
    """

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "CFLStabilityRule"

    def check(
        self,
        config: BaseModel,
        schema: dict,
        build_config: dict
    ) -> list[RuleViolation]:
        """
        Check CFL condition for explicit solver.

        Parameters
        ----------
        config : BaseModel
            Hydrated configuration model.
        schema : dict
            Parameter schema.
        build_config : dict
            Build flags (not used here).

        Returns
        -------
        list of RuleViolation
            Violations for unstable or inefficient CFL values.
        """
        violations = []

        # Get CFL parameter (try multiple aliases)
        cfl = None
        for attr in get_cfl_model_aliases():
            if hasattr(config, attr):
                cfl = getattr(config, attr)
                break

        if cfl is None:
            return violations  # CFL not set, nothing to check

        cfl_value = float(cfl)

        # Stability constraint: CFL ≤ 1.0 for explicit
        if cfl_value > 1.0:
            violations.append(RuleViolation(
                rule_name=self.name,
                severity="error",
                parameter=get_explicit_cfl_param_name(),
                message=f"CFL {cfl_value} > 1.0 violates explicit stability condition.",
                suggested_fix="Reduce cfl to 0.9 or lower for numerical stability."
            ))

        # Efficiency warning: very low CFL
        elif cfl_value < 0.05:
            violations.append(RuleViolation(
                rule_name=self.name,
                severity="warning",
                parameter=get_explicit_cfl_param_name(),
                message=f"CFL {cfl_value} is extremely low. Simulation will be inefficient.",
                suggested_fix="Increase cfl to 0.5-0.9 for better performance."
            ))

        return violations


class BoundaryConditionRule(ValidationRule):
    """
    Ensure geometry periodicity matches boundary condition types.

    Physics: Periodic boundaries require Interior/Periodic BC types.
    Scope: Universal (all AMReX codes).
    """

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "BoundaryConditionRule"

    def check(
        self,
        config: BaseModel,
        schema: dict,
        build_config: dict
    ) -> list[RuleViolation]:
        """
        Check periodic boundary consistency.

        Parameters
        ----------
        config : BaseModel
            Hydrated configuration model.
        schema : dict
            Parameter schema.
        build_config : dict
            Build flags (used for DIM).

        Returns
        -------
        list of RuleViolation
            Violations if periodicity conflicts with BC types.
        """
        violations = []

        # Get periodicity flags
        is_periodic = None
        for attr in ['geometry_is_periodic', 'is_periodic']:
            if hasattr(config, attr):
                is_periodic = getattr(config, attr)
                break

        if is_periodic is None:
            return violations

        # Convert to list if needed
        if isinstance(is_periodic, str):
            is_periodic = [int(x) for x in is_periodic.split()]
        elif isinstance(is_periodic, int):
            is_periodic = [is_periodic]
        elif not isinstance(is_periodic, list):
            is_periodic = list(is_periodic)

        # Check each dimension
        dim = int(build_config.get('DIM', 3))
        for i in range(min(dim, len(is_periodic))):
            if is_periodic[i] == 1:  # Dimension is periodic
                # Check if BC types are set (future enhancement)
                # For now, just validate that periodicity is consistently defined
                pass  # Placeholder for BC type checking

        return violations


class GeometryDomainRule(ValidationRule):
    """
    Validate domain bounds are physically valid.

    Physics: Domain must have positive volume (prob_lo < prob_hi).
    Scope: Universal (all AMReX codes).
    """

    @property
    def name(self) -> str:
        """
        Rule identifier.

        Returns
        -------
        str
            Rule name.
        """
        return "GeometryDomainRule"

    def check(
        self,
        config: BaseModel,
        schema: dict,
        build_config: dict
    ) -> list[RuleViolation]:
        """
        Check domain bounds validity.

        Parameters
        ----------
        config : BaseModel
            Hydrated configuration model.
        schema : dict
            Parameter schema.
        build_config : dict
            Build flags (used for DIM).

        Returns
        -------
        list of RuleViolation
            Violations if prob_lo >= prob_hi.
        """
        violations = []

        # Get domain bounds
        prob_lo = None
        prob_hi = None

        for attr in ['geometry_prob_lo', 'prob_lo']:
            if hasattr(config, attr):
                prob_lo = getattr(config, attr)
                break

        for attr in ['geometry_prob_hi', 'prob_hi']:
            if hasattr(config, attr):
                prob_hi = getattr(config, attr)
                break

        if prob_lo is None or prob_hi is None:
            return violations

        # Convert to lists if needed
        if isinstance(prob_lo, str):
            prob_lo = [float(x) for x in prob_lo.split()]
        elif not isinstance(prob_lo, list):
            prob_lo = [prob_lo]

        if isinstance(prob_hi, str):
            prob_hi = [float(x) for x in prob_hi.split()]
        elif not isinstance(prob_hi, list):
            prob_hi = [prob_hi]

        # Check each dimension
        dim = int(build_config.get('DIM', 3))
        dirs = ['x', 'y', 'z']

        for i in range(min(dim, len(prob_lo), len(prob_hi))):
            if prob_lo[i] >= prob_hi[i]:
                violations.append(RuleViolation(
                    rule_name=self.name,
                    severity="error",
                    parameter=f"geometry.prob_{dirs[i]}",
                    message=f"Domain bound error: prob_lo[{dirs[i]}]={prob_lo[i]} >= prob_hi[{dirs[i]}]={prob_hi[i]}",
                    suggested_fix=f"Ensure prob_lo < prob_hi in {dirs[i]} direction."
                ))

        return violations
