"""
Contract-to-schema alignment checks.

Ensures top-level state keys referenced by tests/contracts remain present in
the canonical GraphState TypedDict.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, Set, get_type_hints

from src.graph import (
    _route_after_clarification,
    _route_after_sweep_detection,
    clarification_handler_node,
    create_graph,
    has_acceptance_checklist_mapped_tests,
    sweep_execution_handler_node,
)
from src.models import GraphState


_SIMPLE_FIELD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_NON_SCHEMA_INPUTS = {"note_on_state_pollution"}


def _iter_contracts() -> Iterable[tuple[Path, dict[str, Any]]]:
    contract_dir = Path(__file__).resolve().parents[1] / "contracts"
    for path in sorted(contract_dir.glob("*.json")):
        yield path, json.loads(path.read_text())


def _collect_top_level_fields(contract: dict[str, Any]) -> Set[str]:
    fields: Set[str] = set()

    required_inputs = contract.get("required_inputs", {})
    for key, value in required_inputs.items():
        if isinstance(value, str):
            if key in _NON_SCHEMA_INPUTS:
                continue
            fields.add(key)

    updates = contract.get("state_updates_returned", {})
    utility = updates.get("utility_flags_top_level_REQUIRED", {})
    if isinstance(utility, dict):
        fields.update(utility.keys())

    pragmatic = updates.get("pragmatic_data_location_OPTIONAL", {})
    allowed_fields = pragmatic.get("allowed_fields", [])
    if isinstance(allowed_fields, list):
        fields.update(
            field for field in allowed_fields if isinstance(field, str)
        )

    checklist = contract.get("schema_compliance_checklist", [])
    if isinstance(checklist, list):
        for entry in checklist:
            if not isinstance(entry, dict):
                continue
            field = entry.get("field")
            if isinstance(field, str) and _SIMPLE_FIELD.match(field):
                fields.add(field)

    return fields


def test_contracts_reference_graphstate_fields() -> None:
    """
    Contract-required top-level fields must exist in the canonical GraphState.
    """
    hints = get_type_hints(GraphState)
    missing_by_contract: dict[str, list[str]] = {}

    for path, contract in _iter_contracts():
        fields = _collect_top_level_fields(contract)
        missing = sorted(field for field in fields if field not in hints)
        if missing:
            missing_by_contract[path.name] = missing

    assert not missing_by_contract, (
        "Contract fields missing from GraphState: "
        f"{missing_by_contract}"
    )


def test_contracts_have_checklists_and_mapped_test_assertions() -> None:
    missing: dict[str, list[str]] = {}

    for path, contract in _iter_contracts():
        # Session 38 targets feature/node contracts, not MCP schema/example files.
        if not isinstance(contract.get("node_name"), str):
            continue

        issues: list[str] = []
        checklist = contract.get("schema_compliance_checklist")
        if not isinstance(checklist, list) or not checklist:
            issues.append("missing schema_compliance_checklist")

        test_cases = contract.get("test_cases")
        if not isinstance(test_cases, list) or not test_cases:
            issues.append("missing test_cases")
        else:
            empty_assertions = [
                case.get("id", "<missing_id>")
                for case in test_cases
                if not isinstance(case, dict)
                or not isinstance(case.get("assertions"), list)
                or not case.get("assertions")
            ]
            if empty_assertions:
                issues.append(
                    f"test cases without assertions: {sorted(empty_assertions)}"
                )

        if issues:
            missing[path.name] = issues

    assert not missing, f"Contracts missing checklist-to-test mapping basics: {missing}"


def test_acceptance_checklist_mapped_tests_helper() -> None:
    valid = {
        "validation_manifest": {
            "acceptance_checklist": [
                {"feature": "f1", "mapped_tests": ["tests/unit/test_a.py::test_x"]},
                {"feature": "f2", "test_ids": ["T-102"]},
                {"feature": "f3", "tests": ["test_behavior"]},
                {"feature": "f4", "test_cases": ["case_1"]},
            ]
        }
    }
    assert has_acceptance_checklist_mapped_tests(valid) is True

    assert has_acceptance_checklist_mapped_tests({}) is False
    assert (
        has_acceptance_checklist_mapped_tests(
            {"validation_manifest": {"acceptance_checklist": []}}
        )
        is False
    )
    assert (
        has_acceptance_checklist_mapped_tests(
            {
                "validation_manifest": {
                    "acceptance_checklist": [{"feature": "missing mappings"}]
                }
            }
        )
        is False
    )


def test_route_after_sweep_detection_requires_acceptance_checklist_mapping(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        "src.graph.is_b4_implementation_sequence_complete",
        lambda _: True,
    )
    monkeypatch.setattr(
        "src.graph.has_checklist_implementation_locations",
        lambda _: True,
    )
    monkeypatch.setattr(
        "src.graph.has_migration_plan_schema_mapping_and_rollback",
        lambda _: True,
    )

    missing_acceptance_map = {
        "sweep_id": "sweep-1",
        "validation_manifest": {"acceptance_checklist": [{"feature": "f1"}]},
    }
    assert _route_after_sweep_detection(missing_acceptance_map) == "architect_node"

    valid = {
        "sweep_id": "sweep-1",
        "validation_manifest": {
            "acceptance_checklist": [{"feature": "f1", "mapped_tests": ["t1"]}]
        },
    }
    assert _route_after_sweep_detection(valid) == "sweep_execution_handler"


def test_graph_helpers_clarification_and_handler_nodes() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == (
        "clarification_handler"
    )
    assert _route_after_clarification({"clarification_needed": False}) == (
        "input_writer_node"
    )

    state = {"clarification_questions": ["need details"], "sweep_id": "sweep-1"}
    assert clarification_handler_node(state) is state
    assert sweep_execution_handler_node(state) is state


def test_graph_compiles_with_acceptance_checklist_gate() -> None:
    app = create_graph().compile()
    graph_def = app.get_graph()
    assert "sweep_detection_node" in graph_def.nodes
