from pathlib import Path

from src.services.inputs_file_selector import InputsFileSelector


def test_select_best_inputs_file_prefers_smallest(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    small = case_dir / "inputs"
    large = case_dir / "inputs.large"
    small.write_text("amr.n_cell = 64 64 64\n")
    large.write_text("x" * 30000)

    selected = InputsFileSelector.select_best_inputs_file(
        case_dir,
        strategy="smallest",
        available_files=[large, small],
    )

    assert selected == small


def test_select_best_inputs_file_returns_none_when_missing(tmp_path):
    case_dir = tmp_path / "empty_case"
    case_dir.mkdir()

    missing = case_dir / "inputs"
    selected = InputsFileSelector.select_best_inputs_file(
        case_dir,
        strategy="smallest",
        available_files=[missing],
    )

    assert selected is None


def test_select_best_inputs_file_llm_compare_honors_prompt_anchor(tmp_path):
    case_dir = tmp_path / "case"
    case_dir.mkdir()

    anelastic = case_dir / "inputs_anelastic"
    compressible = case_dir / "inputs_compressible"
    anelastic.write_text("amr.n_cell = 64 64 64\n")
    compressible.write_text("amr.n_cell = 64 64 64\n")

    selected = InputsFileSelector.select_best_inputs_file(
        case_dir,
        strategy="llm_compare",
        available_files=[compressible, anelastic],
        user_prompt="Please use inputs_anelastic for this baseline.",
    )

    assert selected == anelastic
