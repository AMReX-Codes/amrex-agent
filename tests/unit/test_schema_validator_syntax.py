from src.config import AMReXAgentConfig
from src.services.validators.schema_validator import SchemaSyntaxValidator


def test_schema_validator_syntax_accepts_int_and_real() -> None:
    """PRD Amendment D.3; SchemaSyntaxValidator._validate_type_syntax."""
    validator = SchemaSyntaxValidator(AMReXAgentConfig())

    int_issues = validator._validate_type_syntax("amr.n_cell", "64 64 64", {"type": "IntVect"})
    real_issues = validator._validate_type_syntax("geometry.prob_lo", "0.0 0.5 1.0", {"type": "RealVect"})

    assert int_issues == []
    assert real_issues == []


def test_schema_validator_syntax_flags_invalid_bool_and_power() -> None:
    """Reviewer contract alignment: tests/contracts/reviewer_node_contract.json."""
    validator = SchemaSyntaxValidator(AMReXAgentConfig())

    power_issues = validator._validate_type_syntax("amr.n_cell", "2^8", {"type": "int"})
    bool_issues = validator._validate_type_syntax("amr.regrid_on_restart", "yes", {"type": "bool"})

    assert any(issue.rule_name == "SyntaxFormat" for issue in power_issues)
    assert any(issue.rule_name == "TypeMismatch" for issue in bool_issues)
