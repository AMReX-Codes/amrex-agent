from __future__ import annotations

from pathlib import Path

from src.erf_cases import (
    ERFCaseMatcher,
    discover_erf_cases,
    select_best_erf_case,
)


def _erf_root() -> Path:
    return Path(__file__).resolve().parents[3] / "ERF"


def test_discover_erf_cases_minimum_count_threshold() -> None:
    cases = discover_erf_cases(_erf_root())
    assert len(cases) >= 20


def test_squall_line_discovery_multiple_query_forms() -> None:
    root = _erf_root()
    assert select_best_erf_case("squall line", root) is not None
    assert select_best_erf_case("SquallLine_2D", root) is not None
    assert select_best_erf_case("Exec/CanonicalFlows/SquallLine_2D", root) is not None


def test_nonsense_query_returns_none() -> None:
    root = _erf_root()
    assert select_best_erf_case("xyzzy plugh qwerty asdfgh", root) is None


def test_config_override_precedence() -> None:
    root = _erf_root()
    cases = discover_erf_cases(root)
    matcher = ERFCaseMatcher(
        cases,
        config_weights={"alias": 0.0, "path": 1.0, "tag": 0.0, "name": 0.0, "description": 0.0},
    )
    case = matcher.match("canonical squall line")
    assert case is not None
    assert case.relative_path.startswith("Exec/CanonicalFlows/")
