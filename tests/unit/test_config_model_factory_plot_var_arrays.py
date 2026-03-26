"""ParmParse list coercion tests for visualization plot variable parameters."""

from src.services.config_model_factory import ConfigModelFactory


def _schema_with_plot_var_arrays() -> dict:
    return {
        "amr.plot_vars": {
            "type": "string",
            "is_array": True,
            "required": False,
            "default": None,
        },
        "erf.plot_vars_1": {
            "type": "string",
            "is_array": True,
            "required": False,
            "default": None,
        },
        "peleLM.derive_plot_vars": {
            "type": "string",
            "is_array": True,
            "required": False,
            "default": None,
        },
    }


def test_hydrate_plot_var_arrays_from_whitespace_values():
    model_class = ConfigModelFactory.create_from_schema(
        schema=_schema_with_plot_var_arrays(),
        build_config={},
    )
    hydrated = ConfigModelFactory.hydrate(
        model_class,
        "amr.plot_vars = density temperature\n"
        "erf.plot_vars_1 = qv qc\n"
        "peleLM.derive_plot_vars = temperature heat_release\n",
    )
    assert hydrated.amr_plot_vars == ["density", "temperature"]
    assert hydrated.erf_plot_vars_1 == ["qv", "qc"]
    assert hydrated.peleLM_derive_plot_vars == ["temperature", "heat_release"]


def test_apply_modifications_dedupes_plot_var_array_append_order():
    model_class = ConfigModelFactory.create_from_schema(
        schema=_schema_with_plot_var_arrays(),
        build_config={},
    )
    model = model_class()

    class _Cfg:
        remap_strategy = "append"

    updated = ConfigModelFactory.apply_modifications(
        model,
        [
            ("amr.plot_vars", "density temperature"),
            ("amr.plot_vars", "temperature pressure"),
        ],
        config_service=_Cfg(),
    )
    assert updated.amr_plot_vars == ["density", "temperature", "pressure"]


def test_apply_modifications_plot_var_scalar_to_array_and_last_write():
    model_class = ConfigModelFactory.create_from_schema(
        schema=_schema_with_plot_var_arrays(),
        build_config={},
    )
    model = model_class()
    updated = ConfigModelFactory.apply_modifications(
        model,
        [
            ("erf.plot_vars_1", "qc"),
            ("erf.plot_vars_1", "qv qc"),
        ],
    )
    assert updated.erf_plot_vars_1 == ["qv", "qc"]
