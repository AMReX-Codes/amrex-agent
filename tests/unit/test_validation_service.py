from typing import List

from src.services.validation import ValidationService
from src.services.rules.base import RuleViolation


class _DummyConfigClass:
    @staticmethod
    def validate_config(_config_dict) -> List[RuleViolation]:
        return []


def test_validation_service_valid_complete(monkeypatch) -> None:
    """Reviewer contract alignment: tests/contracts/reviewer_node_contract.json (validation results)."""
    service = ValidationService(config=None)
    monkeypatch.setattr(service, "_resolve_config_class", lambda *_args, **_kwargs: _DummyConfigClass)

    result = service.validate_config({"amr.n_cell": "64 64 64"})

    assert result["valid"] is True
    assert result["complete"] is True
    assert result["errors"] == []
    assert result["warnings"] == []


def test_validation_service_missing_section_is_incomplete(monkeypatch) -> None:
    """GraphState anchor: src/models/graph_state_canonical.py (validation fields)."""
    service = ValidationService(config=None)

    class _ConfigWithMissing:
        @staticmethod
        def validate_config(_config_dict) -> List[RuleViolation]:
            return [
                RuleViolation(
                    rule_name="RequiredSection",
                    severity="warning",
                    message="Missing section",
                )
            ]

    monkeypatch.setattr(service, "_resolve_config_class", lambda *_args, **_kwargs: _ConfigWithMissing)

    result = service.validate_config({"amr.n_cell": "64 64 64"})

    assert result["valid"] is True
    assert result["complete"] is False
    assert result["missing"] == ["Missing section"]
