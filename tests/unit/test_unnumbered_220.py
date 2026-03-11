"""Session 121 tests for standardized router reason codes per execute_planning branch."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.architect import ArchitectService, ROUTER_REASON_CODES
from src.services.plan import SimulationPlan


def _plan(indexing_strategy: str, requirements: dict | None = None) -> SimulationPlan:
    return SimulationPlan(
        selected_solver="PeleC",
        selected_case="Exec/RegTests/PMF",
        modifications=[],
        reasoning="test",
        indexing_strategy=indexing_strategy,
        requirements=requirements,
    )


def _service(config: SimpleNamespace) -> ArchitectService:
    service = ArchitectService.__new__(ArchitectService)
    service.config = config
    service._normalize_baseline_metadata = lambda baseline, selected_case: baseline
    return service


def test_hierarchical_primary_branch_sets_reason_code():
    service = _service(
        SimpleNamespace(indexing_strategy="hierarchical", fallback_to_simple_on_error=True)
    )
    service.create_plan_rag = lambda **_: _plan("hierarchical", {"existing": "value"})
    service.create_plan = lambda **_: pytest.fail("simple path should not be used")

    plan = service.execute_planning(user_prompt="test prompt")

    assert plan.requirements["existing"] == "value"
    assert plan.requirements["router_branch"] == "hierarchical"
    assert plan.requirements["router_reason_code"] == ROUTER_REASON_CODES["hierarchical_primary"]


def test_hierarchical_failure_falls_back_to_simple_with_reason_code():
    service = _service(
        SimpleNamespace(indexing_strategy="hierarchical", fallback_to_simple_on_error=True)
    )

    def _raise(**_kwargs):
        raise RuntimeError("boom")

    service.create_plan_rag = _raise
    service.create_plan = lambda **_: _plan("simple")

    plan = service.execute_planning(user_prompt="test prompt")

    assert plan.requirements["router_branch"] == "simple"
    assert plan.requirements["router_reason_code"] == ROUTER_REASON_CODES["simple_fallback"]


def test_simple_primary_branch_sets_reason_code():
    service = _service(SimpleNamespace(indexing_strategy="simple", fallback_to_simple_on_error=True))
    service.create_plan = lambda **_: _plan("simple")

    plan = service.execute_planning(user_prompt="test prompt")

    assert plan.requirements["router_branch"] == "simple"
    assert plan.requirements["router_reason_code"] == ROUTER_REASON_CODES["simple_primary"]


@pytest.mark.parametrize(
    ("override_strategy", "expected_reason_code"),
    [
        ("override_static", ROUTER_REASON_CODES["override_static"]),
        ("hierarchical", ROUTER_REASON_CODES["override_hierarchical"]),
        ("simple", ROUTER_REASON_CODES["override_simple"]),
    ],
)
def test_override_branches_set_reason_code(override_strategy: str, expected_reason_code: str):
    service = _service(
        SimpleNamespace(indexing_strategy=override_strategy, fallback_to_simple_on_error=True)
    )
    service._execute_planning_with_override = lambda **_: _plan(override_strategy)

    plan = service.execute_planning(
        user_prompt="test prompt",
        baseline_override="PeleC/Exec/RegTests/PMF",
        strategy=override_strategy,
    )

    assert plan.requirements["router_branch"] == override_strategy
    assert plan.requirements["router_reason_code"] == expected_reason_code
