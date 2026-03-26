"""Session 107: UNNUMBERED-166 transient API recovery target tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.config import (
    TRANSIENT_API_RECOVERY_TARGET,
    _LLMRetryCompletions,
    compute_transient_api_recovery_rate,
    evaluate_transient_api_recovery_target,
)


class _TransientError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"status={status_code}")
        self.status_code = status_code


class _BadRequestError(Exception):
    def __init__(self):
        super().__init__("bad request")
        self.status_code = 400


def test_compute_transient_api_recovery_rate_and_target_contract():
    assert compute_transient_api_recovery_rate([]) is None
    assert compute_transient_api_recovery_rate([True, False, True]) == pytest.approx(2 / 3)

    below_target = evaluate_transient_api_recovery_target([True, False])
    assert below_target["transient_recovery_rate"] == pytest.approx(0.5)
    assert below_target["transient_recovery_target"] == TRANSIENT_API_RECOVERY_TARGET
    assert below_target["transient_recovery_target_met"] is False


def test_evaluate_transient_api_recovery_target_falls_back_on_invalid_target():
    result = evaluate_transient_api_recovery_target([True] * 19 + [False], target=4)

    assert result["transient_recovery_target"] == TRANSIENT_API_RECOVERY_TARGET
    assert result["transient_recovery_observations"] == 20
    assert result["transient_recovery_successes"] == 19
    assert result["transient_recovery_rate"] == pytest.approx(0.95)
    assert result["transient_recovery_target_met"] is True


def test_retry_wrapper_records_transient_recovery_rate(monkeypatch):
    side_effect = []
    for _ in range(19):
        side_effect.extend([_TransientError(503), {"ok": True}])
    side_effect.extend([_TransientError(503), _TransientError(503)])

    completions = Mock(side_effect=side_effect)
    wrapper = _LLMRetryCompletions(SimpleNamespace(create=completions), max_attempts=2)

    monkeypatch.setattr("src.config.random.uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr("src.config.time.sleep", lambda _delay: None)

    for _ in range(19):
        assert wrapper.create(model="x", messages=[]) == {"ok": True}

    with pytest.raises(_TransientError):
        wrapper.create(model="x", messages=[])

    status = wrapper.get_transient_recovery_target_status()
    assert status["transient_recovery_observations"] == 20
    assert status["transient_recovery_successes"] == 19
    assert status["transient_recovery_rate"] == pytest.approx(0.95)
    assert status["transient_recovery_target_met"] is True


def test_retry_wrapper_excludes_non_retryable_failures(monkeypatch):
    completions = Mock(side_effect=_BadRequestError())
    wrapper = _LLMRetryCompletions(SimpleNamespace(create=completions), max_attempts=3)

    monkeypatch.setattr("src.config.time.sleep", lambda _delay: None)

    with pytest.raises(_BadRequestError):
        wrapper.create(model="x", messages=[])

    status = wrapper.get_transient_recovery_target_status()
    assert status["transient_recovery_observations"] == 0
    assert status["transient_recovery_rate"] is None
    assert status["transient_recovery_target_met"] is False
