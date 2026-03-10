import builtins
import sys

from src.utils.gate import run_preconfirm_gate


def _sample_options():
    return [
        {"label": "Option A", "value": "option_a"},
        {"label": "Option B", "value": "option_b"},
    ]


def test_preconfirm_gate_non_tty_records_history(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False, raising=False)

    result = run_preconfirm_gate(
        node_name="architect",
        summary_lines=["Summary line"],
        options=_sample_options(),
        enabled=True,
    )

    assert result["action"] == "skipped"
    history = result["history_entry"]
    assert history["node"] == "preconfirm_gate"
    assert history["details"]["gate_type"] == "preconfirm"
    assert history["details"]["decision_type"] == "skip"
    assert history["details"]["reason"] == "non_tty"
    assert history["details"]["options_count"] == 2


def test_preconfirm_gate_auto_approve_records_selection(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)

    result = run_preconfirm_gate(
        node_name="runner_compile",
        summary_lines=["Summary line"],
        options=_sample_options(),
        enabled=True,
        auto_approve=True,
    )

    assert result["action"] == "proceed"
    history = result["history_entry"]
    assert history["details"]["gate_type"] == "preconfirm"
    assert history["details"]["decision_type"] == "select"
    assert history["details"]["selected_index"] == 1
    assert history["details"]["selection"]["value"] == "option_a"


def test_preconfirm_gate_cancel_records_decision(monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(builtins, "input", lambda _: "c")

    result = run_preconfirm_gate(
        node_name="reviewer",
        summary_lines=["Summary line"],
        options=_sample_options(),
        enabled=True,
        allow_cancel=True,
    )

    assert result["action"] == "cancel"
    history = result["history_entry"]
    assert history["details"]["gate_type"] == "preconfirm"
    assert history["details"]["decision_type"] == "cancel"
    assert history["details"]["choice"] == "c"
