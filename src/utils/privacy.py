"""Privacy scrubbing utilities for prompts and persisted artifacts."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)


class PrivacyViolation(RuntimeError):
    pass


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PATH_RE = re.compile(r"(?:/home/[^\s/]+/|/Users/[^\s/]+/|C:\\Users\\[^\s\\]+\\)")
_JWT_RE = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
_PEM_RE = re.compile(r"-----BEGIN [A-Z0-9 _-]+-----.*?-----END [A-Z0-9 _-]+-----", re.DOTALL)
_API_KEY_RE = re.compile(r"(?i)(api_key|apikey|token|secret)\s*[:=]\s*[^\s]+")
_SK_RE = re.compile(r"sk-[A-Za-z0-9]{20,}")

_SENSITIVE_KEYS = {
    "prompt",
    "user_prompt",
    "prompt_text",
    "messages",
    "content",
    "reasoning",
    "inputs_content",
    "question",
    "answer",
    "query",
    "raw_prompt",
}


@dataclass(frozen=True)
class ScrubResult:
    text: str
    hash: str
    detections: list[str]


def _hash_text(text: str, salt: str | None) -> str:
    digest = hashlib.sha256()
    if salt:
        digest.update(salt.encode("utf-8"))
    digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def _detect(text: str) -> list[str]:
    detections: list[str] = []
    if _EMAIL_RE.search(text):
        detections.append("email")
    if _PATH_RE.search(text):
        detections.append("path")
    if _JWT_RE.search(text):
        detections.append("jwt")
    if _PEM_RE.search(text):
        detections.append("pem")
    if _API_KEY_RE.search(text) or _SK_RE.search(text):
        detections.append("key")
    return detections


def get_privacy_mode(config: Any | None) -> str:
    return getattr(config, "privacy_mode", "off") if config is not None else "off"


def get_privacy_scrubber(config: Any | None) -> str:
    return getattr(config, "privacy_scrubber", "builtin") if config is not None else "builtin"


def get_privacy_salt(config: Any | None) -> str | None:
    return getattr(config, "privacy_hash_salt", None) if config is not None else None


def should_scrub_key(key: str) -> bool:
    return key in _SENSITIVE_KEYS


def _scrub_with_builtin(text: str, mode: str) -> tuple[str, list[str]]:
    detections = _detect(text)
    redacted = text
    if mode == "shared":
        if detections:
            redacted = _PEM_RE.sub("[REDACTED:PEM]", redacted)
            redacted = _SK_RE.sub("[REDACTED:KEY]", redacted)
            redacted = _API_KEY_RE.sub(r"\1=[REDACTED:KEY]", redacted)
            redacted = _JWT_RE.sub("[REDACTED:JWT]", redacted)
            redacted = _EMAIL_RE.sub("[REDACTED:EMAIL]", redacted)
            redacted = _PATH_RE.sub("[REDACTED:PATH]", redacted)
    elif mode == "strict":
        redacted = "[REDACTED:HASH]"
    return redacted, detections


def _scrub_with_scrubadub(text: str) -> tuple[str, list[str]]:
    try:
        import scrubadub
    except (ImportError, ModuleNotFoundError):
        logger.warning("privacy_scrubber=scrubadub requested but scrubadub is not installed; using builtin.")
        return _scrub_with_builtin(text, "shared")
    scrubber = scrubadub.Scrubber()
    redacted = scrubber.scrub(text)
    detections = ["scrubadub"] if redacted != text else []
    return redacted, detections


def _scrub_with_presidio(text: str) -> tuple[str, list[str]]:
    try:
        from presidio_analyzer import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine
    except (ImportError, ModuleNotFoundError):
        logger.warning("privacy_scrubber=presidio requested but presidio is not installed; using builtin.")
        return _scrub_with_builtin(text, "shared")
    try:
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        results = analyzer.analyze(text=text, language="en")
        anonymized = anonymizer.anonymize(text=text, analyzer_results=results)
        redacted = anonymized.text
        detections = ["presidio"] if redacted != text else []
        return redacted, detections
    except Exception:
        logger.warning("privacy_scrubber=presidio failed to initialize; using builtin.")
        return _scrub_with_builtin(text, "shared")


def scrub_text(
    text: str,
    *,
    mode: str,
    salt: str | None = None,
    config: Any | None = None,
) -> ScrubResult:
    scrubber = get_privacy_scrubber(config)
    if mode == "shared" and scrubber != "builtin":
        if scrubber == "scrubadub":
            redacted, detections = _scrub_with_scrubadub(text)
        else:
            redacted, detections = _scrub_with_presidio(text)
        return ScrubResult(text=redacted, hash=_hash_text(text, salt), detections=detections)

    redacted, detections = _scrub_with_builtin(text, mode)
    return ScrubResult(text=redacted, hash=_hash_text(text, salt), detections=detections)


def sanitize_payload(
    payload: Any,
    *,
    config: Any | None,
    mode: str | None = None,
    sensitive_keys: Iterable[str] | None = None,
) -> Any:
    if mode is None:
        mode = get_privacy_mode(config)
    if mode == "off":
        return payload

    salt = get_privacy_salt(config)
    sensitive = set(sensitive_keys) if sensitive_keys is not None else _SENSITIVE_KEYS

    if isinstance(payload, dict):
        sanitized: dict[str, Any] = {}
        for key, value in payload.items():
            if isinstance(value, str) and (key in sensitive or _detect(value)):
                result = scrub_text(value, mode=mode, salt=salt, config=config)
                if mode == "strict" and key in sensitive:
                    sanitized[key] = result.hash
                else:
                    sanitized[key] = result.text
                continue
            sanitized[key] = sanitize_payload(
                value,
                config=config,
                mode=mode,
                sensitive_keys=sensitive,
            )
        return sanitized

    if isinstance(payload, list):
        return [
            sanitize_payload(item, config=config, mode=mode, sensitive_keys=sensitive)
            for item in payload
        ]

    if isinstance(payload, tuple):
        return tuple(
            sanitize_payload(item, config=config, mode=mode, sensitive_keys=sensitive)
            for item in payload
        )

    if isinstance(payload, str):
        if _detect(payload):
            result = scrub_text(payload, mode=mode, salt=salt, config=config)
            return result.hash if mode == "strict" else result.text
        return payload

    return payload


def enforce_strict(text: str, *, config: Any | None, purpose: str) -> None:
    mode = get_privacy_mode(config)
    if mode != "strict":
        return
    detections = _detect(text)
    if detections:
        raise PrivacyViolation(f"Privacy mode strict blocked {purpose}: {detections}")
