from pydantic import BaseModel

from src.services.rules.physics import BoundaryConditionRule, GeometryDomainRule


def test_boundary_condition_rule_accepts_periodic_strings() -> None:
    """Reviewer contract alignment: tests/contracts/reviewer_node_contract.json (validation behavior)."""

    class _PeriodicConfig(BaseModel):
        geometry_is_periodic: str = "1 0 0"

    rule = BoundaryConditionRule()
    violations = rule.check(_PeriodicConfig(), {}, {"DIM": "3"})

    assert violations == []


def test_geometry_domain_rule_detects_invalid_bounds() -> None:
    """GraphState anchor: src/models/graph_state_canonical.py (validation results)."""

    class _DomainConfig(BaseModel):
        geometry_prob_lo: str = "0.0 0.0 0.0"
        geometry_prob_hi: str = "0.0 1.0 1.0"

    rule = GeometryDomainRule()
    violations = rule.check(_DomainConfig(), {}, {"DIM": "3"})

    assert violations
    assert violations[0].parameter == "geometry.prob_x"
