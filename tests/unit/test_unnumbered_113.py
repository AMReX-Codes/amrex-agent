"""Session 94 tests for UNNUMBERED-113 Tier 3/4 non-blocking logging."""

from __future__ import annotations

import logging

from database.scripts.build_schema import SchemaBuilder


def test_tier3_and_tier4_issues_are_logged_without_blocking(tmp_path, caplog) -> None:
    builder = SchemaBuilder(tmp_path)
    builder.schema = {
        "pelec.cfl": {"priority": "tier1"},
        "amr.blocking_factor": {"priority": "tier3"},
        "runtime.hint": {"priority": "tier4"},
    }

    with caplog.at_level(logging.INFO):
        builder._log_non_blocking_tier34_issues()

    assert "Tier 3 non-blocking logging: 1 optional parameter(s) detected." in caplog.text
    assert "Tier 4 non-blocking logging: 1 informational parameter(s) detected." in caplog.text


def test_unknown_priority_is_treated_as_tier4_without_blocking(tmp_path, caplog) -> None:
    builder = SchemaBuilder(tmp_path)
    builder.schema = {
        "amr.max_grid_size": {"priority": "experimental"},
    }

    with caplog.at_level(logging.INFO):
        builder._log_non_blocking_tier34_issues()

    assert "Unknown priority 'experimental' for parameter 'amr.max_grid_size'" in caplog.text
    assert "Tier 4 non-blocking logging: 1 informational parameter(s) detected." in caplog.text


def test_scan_source_code_invokes_tier34_non_blocking_logging(tmp_path, monkeypatch) -> None:
    builder = SchemaBuilder(tmp_path)
    calls = {"count": 0}

    def _record_call() -> None:
        calls["count"] += 1

    monkeypatch.setattr(builder, "_log_non_blocking_tier34_issues", _record_call)
    builder.scan_source_code(source_dirs=[])

    assert calls["count"] == 1
