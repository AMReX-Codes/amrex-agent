from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


def _load_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def test_mcp_contract_examples_match_schema() -> None:
    contract_dir = Path(__file__).resolve().parents[1] / "contracts"
    schema_examples = [
        ("mcp_prompt_to_plotfile_schema.json", "mcp_prompt_to_plotfile_example.json"),
        ("mcp_prompt_to_slicefile_schema.json", "mcp_prompt_to_slicefile_example.json"),
    ]

    for schema_name, example_name in schema_examples:
        schema_path = contract_dir / schema_name
        example_path = contract_dir / example_name
        schema = _load_json(schema_path)
        example = _load_json(example_path)

        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(example), key=lambda error: list(error.path))
        assert not errors, (
            f"{example_path.name} does not match {schema_path.name}: "
            f"{[error.message for error in errors]}"
        )
