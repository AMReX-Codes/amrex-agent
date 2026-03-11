"""Session 52: DRY refactor coverage for UNNUMBERED-003."""

from src.services.plan import SimulationPlanFactory, normalize_unnumbered_003


def test_normalize_unnumbered_003_converts_dict_modifications() -> None:
    payload = [{"parameter": "amr.n_cell", "value": "64 64 64"}]

    normalized = normalize_unnumbered_003(payload)

    assert normalized == [("amr.n_cell", "64 64 64")]


def test_normalize_unnumbered_003_converts_list_modifications() -> None:
    payload = [["max_step", 100], ["stop_time", 1.0]]

    normalized = normalize_unnumbered_003(payload)

    assert normalized == [("max_step", 100), ("stop_time", 1.0)]


def test_create_from_rag_uses_normalized_modifications() -> None:
    baseline_result = {
        "selected_case": {"case": "Exec/CaseA", "metadata": {"repo_path": "Exec/CaseA"}},
        "confidence": 0.9,
        "candidates": [],
    }
    cbr_plan = {
        "modifications": [{"parameter": "max_step", "value": 5}],
        "confidence": 0.7,
        "reasoning": "",
        "similar_cases": ["CaseA"],
    }

    plan = SimulationPlanFactory.create_from_rag(
        solver_name="PeleC",
        baseline_result=baseline_result,
        cbr_plan=cbr_plan,
        docs=[],
        user_prompt="run a short test",
    )

    assert plan.modifications == [("max_step", 5)]


def test_from_dict_normalizes_list_modifications() -> None:
    hydrated = SimulationPlanFactory.from_dict(
        {
            "selected_solver": "PeleC",
            "selected_case": "Exec/CaseB",
            "modifications": [["amr.max_level", 2]],
            "reasoning": "legacy list",
        }
    )

    assert hydrated.modifications == [("amr.max_level", 2)]


def test_migrate_legacy_dict_normalizes_dict_modifications() -> None:
    migrated = SimulationPlanFactory._migrate_legacy_dict(
        {
            "solver": "PeleC",
            "baseline": {"path": "Exec/CaseC", "code": "PeleC"},
            "modifications": [{"parameter": "cfl", "value": 0.8}],
        }
    )

    assert migrated["modifications"] == [("cfl", 0.8)]
