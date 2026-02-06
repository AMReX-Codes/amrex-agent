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
