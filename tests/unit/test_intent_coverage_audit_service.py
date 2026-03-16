from types import SimpleNamespace

from src.services.intent_coverage_audit import IntentCoverageAuditService


def test_audit_detects_missing_explicit_assignment() -> None:
    service = IntentCoverageAuditService(SimpleNamespace())
    result = service.audit(
        prompt="Set max_step = 10 and dt = 20.",
        plan={"modifications": [("max_step", "10")]},
    )

    assert result["requires_intent_resolution"] is True
    assert ("dt", "20") in result["unresolved_requests"]
    assert result["reason_code"] == "intent_missing"


def test_audit_treats_dt_as_covered_by_fixed_dt() -> None:
    service = IntentCoverageAuditService(SimpleNamespace())
    result = service.audit(
        prompt="Set dt = 20",
        plan={"modifications": [("erf.fixed_dt", "20")]},
    )

    assert result["requires_intent_resolution"] is False
    assert result["unresolved_requests"] == []
