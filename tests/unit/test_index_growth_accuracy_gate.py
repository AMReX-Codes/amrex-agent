"""Tests for index-growth accuracy drift control."""

from pathlib import Path

import pytest

from database.indexing.level0_searcher import Level0Searcher


@pytest.fixture
def searcher() -> Level0Searcher:
    return Level0Searcher(index_dir=Path("mock"))


@pytest.mark.parametrize(
    ("index_count", "baseline", "current", "expected_gate_active", "expected_passed"),
    [
        (99, 0.95, 0.92, False, True),
        (100, 0.95, 0.93, True, True),
        (150, 0.95, 0.929, True, False),
        (120, 0.90, 0.94, True, True),
    ],
)
def test_index_growth_accuracy_drift_contract(
    searcher: Level0Searcher,
    index_count: int,
    baseline: float,
    current: float,
    expected_gate_active: bool,
    expected_passed: bool,
) -> None:
    verdict = searcher.evaluate_index_growth_accuracy_drift(
        baseline_accuracy=baseline,
        current_accuracy=current,
        index_count=index_count,
    )

    assert verdict["index_count"] == index_count
    assert verdict["gate_active"] is expected_gate_active
    assert verdict["passed"] is expected_passed

    expected_drop = max(0.0, baseline - current)
    assert verdict["accuracy_drop"] == pytest.approx(expected_drop)
    assert verdict["max_allowed_accuracy_drop"] == pytest.approx(0.02)
    assert verdict["min_index_growth_threshold"] == 100


def test_index_growth_accuracy_drift_uses_loaded_index_count(
    searcher: Level0Searcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(searcher, "_count_index_entries", lambda: 137)

    verdict = searcher.evaluate_index_growth_accuracy_drift(
        baseline_accuracy=0.96,
        current_accuracy=0.95,
    )

    assert verdict["index_count"] == 137
    assert verdict["gate_active"] is True
    assert verdict["drift_within_target"] is True
    assert verdict["passed"] is True


def test_index_growth_accuracy_drift_count_uses_max_subindex_population(
    searcher: Level0Searcher,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeIndex:
        def __init__(self, n: int) -> None:
            self.ntotal = n

    searcher.indices = {
        "physics_regimes": _FakeIndex(25),
        "solver_capabilities": _FakeIndex(20),
        "code_lineage": _FakeIndex(15),
        "cross_cutting_guidance": _FakeIndex(10),
    }
    monkeypatch.setattr(searcher, "_load_index", lambda _name: None)

    verdict = searcher.evaluate_index_growth_accuracy_drift(
        baseline_accuracy=0.95,
        current_accuracy=0.90,
    )

    assert verdict["index_count"] == 25
    assert verdict["gate_active"] is False


@pytest.mark.parametrize("baseline,current", [(-0.1, 0.9), (0.9, 1.1)])
def test_index_growth_accuracy_drift_rejects_invalid_accuracy_values(
    searcher: Level0Searcher,
    baseline: float,
    current: float,
) -> None:
    with pytest.raises(ValueError):
        searcher.evaluate_index_growth_accuracy_drift(
            baseline_accuracy=baseline,
            current_accuracy=current,
            index_count=120,
        )
