from pydantic import BaseModel, ConfigDict, Field

from src.services.rules.common import BuildFlagDependencyRule, GridConsistencyRule


class _ConfigWithAlias(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    erf_moisture_model: str = Field(default="1", alias="erf.moisture_model")


def test_build_flag_dependency_rule_normalizes_prefix() -> None:
    """PRD Amendment D.3; underscores -> dotted schema match in BuildFlagDependencyRule."""
    rule = BuildFlagDependencyRule()
    config = _ConfigWithAlias()
    schema = {"erf.moisture_model": {"dependencies": ["ERF_USE_MOISTURE"]}}
    build_config = {"USE_MOISTURE": "FALSE"}

    violations = rule.check(config, schema, build_config)

    assert violations
    assert violations[0].parameter == "erf.moisture_model"


def test_grid_consistency_auto_corrects_blocking_factor() -> None:
    """GraphState anchor: src/models/graph_state_canonical.py (parameter validation)."""
    rule = GridConsistencyRule()

    class _GridConfig(BaseModel):
        amr_n_cell: list[int] = [64, 64, 64]
        amr_blocking_factor: int = 7

    config = _GridConfig()
    violations = rule.check(config, {}, {})

    assert violations
    updated = rule.auto_correct(config, violations[0])
    assert updated.amr_blocking_factor in {1, 2, 4, 8, 16, 32, 64}
