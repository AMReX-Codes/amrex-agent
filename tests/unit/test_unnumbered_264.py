"""Session 136 tests for polling outcomes + latency logging."""

from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

from src.services.run_superfacility_tools import monitor_job


def test_monitor_job_logs_sbatch_poll_outcomes_and_latencies(monkeypatch, caplog):
    run_count = {"value": 0}

    def fake_run(_cmd, capture_output=True, text=True):
        run_count["value"] += 1
        if run_count["value"] == 1:
            return SimpleNamespace(stdout="RUNNING")
        return SimpleNamespace(stdout="")

    times = iter([100.0, 100.025, 101.0, 101.040])

    monkeypatch.setattr("subprocess.run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr("time.perf_counter", lambda: next(times))

    with caplog.at_level(logging.INFO, logger="src.services.run_superfacility_tools"):
        state = monitor_job(job_id="123", method="sbatch", poll_interval=0, max_polls=2)

    assert state == "COMPLETED"

    poll_messages = [record.message for record in caplog.records if "Job poll" in record.message]
    assert len(poll_messages) == 2
    assert "method=sbatch" in poll_messages[0]
    assert "outcome=RUNNING" in poll_messages[0]
    assert "latency_ms=25.000" in poll_messages[0]
    assert "method=sbatch" in poll_messages[1]
    assert "outcome=COMPLETED" in poll_messages[1]
    assert "latency_ms=40.000" in poll_messages[1]


def test_monitor_job_logs_api_terminal_outcome_latency(monkeypatch, caplog):
    class DummyResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"status": "FAILED"}

    times = iter([200.0, 200.010])

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=lambda *_args, **_kwargs: DummyResponse()))
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr("time.perf_counter", lambda: next(times))

    with caplog.at_level(logging.INFO, logger="src.services.run_superfacility_tools"):
        state = monitor_job(
            job_id="789",
            method="api",
            poll_interval=0,
            max_polls=1,
            nersc_session={"type": "token", "token": "abc"},
        )

    assert state == "FAILED"

    poll_messages = [record.message for record in caplog.records if "Job poll" in record.message]
    assert len(poll_messages) == 1
    assert "method=api" in poll_messages[0]
    assert "outcome=FAILED" in poll_messages[0]
    assert "latency_ms=10.000" in poll_messages[0]
