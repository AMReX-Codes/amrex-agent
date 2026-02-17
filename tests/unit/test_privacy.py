from src.utils.privacy import (
    PrivacyViolation,
    detect_text,
    enforce_strict,
    sanitize_payload,
    scrub_log_message,
    scrub_text,
)


class DummyConfig:
    def __init__(self, mode):
        self.privacy_mode = mode
        self.privacy_hash_salt = "salt"


def test_scrub_text_shared_redacts_markers():
    text = "email me at user@example.com and use sk-abcdefghijklmnopqrstuv"
    result = scrub_text(text, mode="shared", salt="salt")
    assert "[REDACTED:EMAIL]" in result.text
    assert "[REDACTED:KEY]" in result.text
    assert result.hash


def test_sanitize_payload_shared_redacts_sensitive_key():
    payload = {"prompt": "reach me at user@example.com"}
    result = sanitize_payload(payload, config=DummyConfig("shared"))
    assert result["prompt"] != payload["prompt"]
    assert "[REDACTED:EMAIL]" in result["prompt"]


def test_sanitize_payload_strict_hashes_sensitive_key():
    payload = {"prompt": "reach me at user@example.com"}
    result = sanitize_payload(payload, config=DummyConfig("strict"))
    assert result["prompt"] != payload["prompt"]
    assert len(result["prompt"]) == 64


def test_enforce_strict_blocks_on_detection():
    config = DummyConfig("strict")
    try:
        enforce_strict("path /home/user/secret", config=config, purpose="unit_test")
    except PrivacyViolation as exc:
        assert "unit_test" in str(exc)
    else:
        raise AssertionError("PrivacyViolation not raised")


def test_scrub_log_message_shared_redacts():
    config = DummyConfig("shared")
    message = "contact user@example.com"
    assert "user@example.com" in message
    scrubbed = scrub_log_message(message, config=config)
    assert "user@example.com" not in scrubbed
    assert "[REDACTED:EMAIL]" in scrubbed


def test_detect_text_reports_matches():
    detections = detect_text("token=abc123 user@example.com")
    assert "email" in detections
