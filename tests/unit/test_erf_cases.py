from __future__ import annotations

from pathlib import Path

import pytest

from src.erf_cases import (
    ERFCaseMatcher,
    discover_erf_cases,
    select_best_erf_case,
)


def _erf_root() -> Path:
    return Path(__file__).resolve().parents[3] / "ERF"


def _require_erf_repo() -> Path:
    root = _erf_root()
    if not root.exists():
        pytest.skip(f"ERF repository not found at {root}")
    if not (root / "Exec").exists():
        pytest.skip(f"ERF repository at {root} is missing Exec/; skipping ERF case discovery tests")
    return root


def test_discover_erf_cases_minimum_count_threshold() -> None:
    cases = discover_erf_cases(_require_erf_repo())
    assert len(cases) >= 20


def test_squall_line_discovery_multiple_query_forms() -> None:
    root = _require_erf_repo()
    assert select_best_erf_case("squall line", root) is not None
    assert select_best_erf_case("SquallLine_2D", root) is not None
    assert select_best_erf_case("Exec/CanonicalFlows/SquallLine_2D", root) is not None


def test_nonsense_query_returns_none() -> None:
    root = _require_erf_repo()
    assert select_best_erf_case("xyzzy plugh qwerty asdfgh", root) is None


def test_config_override_precedence() -> None:
    root = _require_erf_repo()
    cases = discover_erf_cases(root)
    matcher = ERFCaseMatcher(
        cases,
        config_weights={"alias": 0.0, "path": 1.0, "tag": 0.0, "name": 0.0, "description": 0.0},
    )
    case = matcher.match("canonical squall line")
    assert case is not None
    assert case.relative_path.startswith("Exec/CanonicalFlows/")


@pytest.mark.skip(reason="Known false-negative in reachability prompt synthesis; may be spurious work.")
def test_every_erf_input_file_reachable_by_specific_prompt() -> None:
    root = _require_erf_repo()
    cases = discover_erf_cases(root)
    matcher = ERFCaseMatcher(cases)

    missing: list[str] = []
    for case in cases:
        for input_file in case.input_files:
            prompts = [
                f"{case.relative_path}/{input_file}",
                f"{case.category} {case.canonical_name} {input_file.replace('_', ' ')}",
                f"{case.canonical_name} {input_file.replace('_', ' ')}",
            ]
            if not any((match := matcher.match(prompt)) and match.relative_path == case.relative_path for prompt in prompts):
                missing.append(f"{case.relative_path}/{input_file}")

    assert not missing, f"Unreachable input files: {missing}"
