"""Session 69 tests for UNNUMBERED-023 DRY normalization refactor."""

from __future__ import annotations

from src.services.plan import SimulationPlanFactory, normalize_unnumbered_023


def test_normalize_unnumbered_023_supports_tuple_list_and_dict_inputs() -> None:
    normalized = normalize_unnumbered_023(
        [
            ("amr.n_cell", "64 64 64"),
            ["amr.max_level", "2"],
            {"parameter": "amr.plot_int", "value": "10"},
            "ignore-me",
            {"other": "ignore-missing-keys"},
        ]
    )

    assert normalized == [
        ("amr.n_cell", "64 64 64"),
        ("amr.max_level", "2"),
        ("amr.plot_int", "10"),
        ("", ""),
    ]


def test_create_from_rag_uses_normalize_unnumbered_023_for_modifications() -> None:
    plan = SimulationPlanFactory.create_from_rag(
        solver_name="AMReX",
        baseline_result={"selected_case": {"case": "Exec/Advection"}},
        cbr_plan={
            "modifications": [
                ["amr.max_level", "1"],
                {"parameter": "amr.n_cell", "value": "128 128 128"},
            ],
            "reasoning": "normalized",
        },
        docs=[],
        user_prompt="advection",
    )

    assert plan.modifications == [
        ("amr.max_level", "1"),
        ("amr.n_cell", "128 128 128"),
    ]


def test_from_dict_uses_normalize_unnumbered_023_for_modifications() -> None:
    plan = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleC",
            "selected_case": "Exec/Flame",
            "modifications": [
                ["amr.max_level", "2"],
                {"parameter": "amr.plot_int", "value": "5"},
            ],
            "reasoning": "from dict",
        }
    )

    assert plan.modifications == [("amr.max_level", "2"), ("amr.plot_int", "5")]


def test_legacy_migration_uses_normalize_unnumbered_023_for_modifications() -> None:
    plan = SimulationPlanFactory.from_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/Flame", "code": "PeleC"},
            "modifications": [
                {"parameter": "amr.max_level", "value": "1"},
                ["amr.plot_int", "10"],
            ],
        }
    )

    assert plan.modifications == [("amr.max_level", "1"), ("amr.plot_int", "10")]
