"""Session 12: B4.7 new CLI argument coverage."""

from __future__ import annotations

import argparse

import pytest

from src.graph import _route_after_clarification, _route_after_paper_validator
from src.main import initialize_state, load_prompt_content, parse_arguments


class _DummyConfig:
    max_iterations = 3


def test_parse_arguments_requires_prompt_or_paper_source() -> None:
    with pytest.raises(SystemExit):
        parse_arguments([])


def test_parse_arguments_prompt_only_keeps_validator_disabled() -> None:
    parsed = parse_arguments(["--prompt", "run case"])
    assert parsed.prompt == "run case"
    assert parsed.paper_source is None
    assert parsed.paper_validator_enabled is False


def test_parse_arguments_arxiv_source_infers_input_type() -> None:
    parsed = parse_arguments(["--paper-source", "2401.12345"])
    assert parsed.paper_source == "2401.12345"
    assert parsed.paper_input_type == "arxiv"
    assert parsed.paper_validator_enabled is True


def test_parse_arguments_pdf_source_infers_input_type(tmp_path) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF")

    parsed = parse_arguments(["--paper-source", str(pdf_path)])
    assert parsed.paper_input_type == "pdf"
    assert parsed.paper_validator_enabled is True


def test_parse_arguments_tex_directory_infers_pdf_tex(tmp_path) -> None:
    tex_dir = tmp_path / "paper_tex"
    tex_dir.mkdir()

    parsed = parse_arguments(["--paper-source", str(tex_dir)])
    assert parsed.paper_input_type == "pdf+tex"
    assert parsed.paper_validator_enabled is True


def test_parse_arguments_paper_type_without_source_fails() -> None:
    with pytest.raises(SystemExit):
        parse_arguments(["--prompt", "x", "--paper-input-type", "pdf"])


def test_parse_arguments_unknown_source_requires_explicit_type(tmp_path) -> None:
    unknown = tmp_path / "paper.txt"
    unknown.write_text("plain text", encoding="utf-8")

    with pytest.raises(SystemExit):
        parse_arguments(["--paper-source", str(unknown)])


def test_parse_arguments_accepts_explicit_paper_input_type_for_unknown_source(tmp_path) -> None:
    unknown = tmp_path / "paper.dat"
    unknown.write_text("placeholder", encoding="utf-8")

    parsed = parse_arguments([
        "--paper-source",
        str(unknown),
        "--paper-input-type",
        "pdf",
    ])
    assert parsed.paper_input_type == "pdf"
    assert parsed.paper_validator_enabled is True


def test_load_prompt_content_returns_empty_when_prompt_missing_in_paper_mode() -> None:
    args = argparse.Namespace(prompt=None, prompt_path=None)
    assert load_prompt_content(args) == ""


def test_load_prompt_content_reads_prompt_path(tmp_path) -> None:
    prompt_path = tmp_path / "request.txt"
    prompt_path.write_text("simulate flame", encoding="utf-8")

    args = argparse.Namespace(prompt=None, prompt_path=str(prompt_path))
    assert load_prompt_content(args) == "simulate flame"


def test_initialize_state_carries_paper_fields() -> None:
    state = initialize_state(
        "",
        _DummyConfig(),
        paper_source="2401.12345",
        paper_input_type="arxiv",
        paper_validator_enabled=True,
    )
    assert state["paper_source"] == "2401.12345"
    assert state["paper_input_type"] == "arxiv"
    assert state["paper_validator_enabled"] is True


def test_initialize_state_generates_prompt_for_paper_only_mode() -> None:
    state = initialize_state(
        "",
        _DummyConfig(),
        paper_source="2401.12345",
        paper_input_type="arxiv",
        paper_validator_enabled=True,
    )
    assert state["prompt"]
    assert "2401.12345" in state["prompt"]


def test_route_after_paper_validator_respects_flag_and_source() -> None:
    assert _route_after_paper_validator({"paper_validator_enabled": True}) == "paper_validator_node"
    assert _route_after_paper_validator({"paper_source": "2401.12345"}) == "paper_validator_node"
    assert _route_after_paper_validator({"paper_input_type": "arxiv"}) == "paper_validator_node"
    assert _route_after_paper_validator({}) == "input_writer_node"


def test_route_after_clarification_uses_paper_validator_route() -> None:
    assert _route_after_clarification({"clarification_needed": True}) == "clarification_handler"
    assert _route_after_clarification({"clarification_needed": False}) == "input_writer_node"
    assert _route_after_clarification(
        {"clarification_needed": False, "paper_source": "2401.12345"}
    ) == "paper_validator_node"
