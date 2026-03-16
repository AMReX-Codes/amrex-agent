"""Intent coverage audit for reviewer pre-execution validation."""

from __future__ import annotations

import re
from typing import Any


class IntentCoverageAuditService:
    """Detect prompt-requested explicit assignments that are missing from plan modifications."""

    _ASSIGNMENT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*([^\s,;]+)")

    def __init__(self, config: Any):
        self.config = config

    def audit(self, *, prompt: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Return structured intent coverage findings."""
        requests = self._extract_requested_assignments(prompt)
        if not requests:
            return self._empty_result()

        modifications = plan.get("modifications", [])
        mod_items = self._normalize_modifications(modifications)

        missing: list[tuple[str, str]] = []
        for requested_param, requested_value in requests:
            if not self._is_covered(requested_param, mod_items):
                missing.append((requested_param, requested_value))

        if not missing:
            return self._empty_result()

        guidance_lines = ", ".join(f"{name}={value}" for name, value in missing)
        return {
            "requires_intent_resolution": True,
            "unresolved_requests": missing,
            "resolution_guidance": (
                "Preserve explicit user-requested assignments in planned modifications before approval. "
                f"Missing assignments: {guidance_lines}"
            ),
            "suggested_modifications": dict(missing),
            "reason_code": "intent_missing",
        }

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {
            "requires_intent_resolution": False,
            "unresolved_requests": [],
            "resolution_guidance": "",
            "suggested_modifications": {},
            "reason_code": None,
        }

    def _extract_requested_assignments(self, prompt: str) -> list[tuple[str, str]]:
        if not isinstance(prompt, str) or not prompt.strip():
            return []
        results: list[tuple[str, str]] = []
        for match in self._ASSIGNMENT_RE.finditer(prompt):
            key = self._normalize_key(match.group(1))
            value = match.group(2).strip().rstrip(".,;")
            if not key:
                continue
            results.append((key, value))
        return results

    @staticmethod
    def _normalize_modifications(modifications: Any) -> list[tuple[str, Any]]:
        if isinstance(modifications, dict):
            return [(str(k), v) for k, v in modifications.items()]
        if isinstance(modifications, list):
            pairs: list[tuple[str, Any]] = []
            for item in modifications:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    pairs.append((str(item[0]), item[1]))
            return pairs
        return []

    @staticmethod
    def _normalize_key(name: str) -> str:
        text = str(name or "").strip().lower().replace("-", "_")
        while "__" in text:
            text = text.replace("__", "_")
        return text

    def _is_covered(self, requested_param: str, modifications: list[tuple[str, Any]]) -> bool:
        requested_norm = self._normalize_key(requested_param)
        for modified_param, _value in modifications:
            modified_norm = self._normalize_key(modified_param)
            if self._keys_match(requested_norm, modified_norm):
                return True
        return False

    def _keys_match(self, requested_norm: str, modified_norm: str) -> bool:
        if requested_norm == modified_norm:
            return True
        if modified_norm.endswith(f".{requested_norm}") or modified_norm.endswith(f"_{requested_norm}"):
            return True

        requested_tokens = self._tokenize(requested_norm)
        modified_tokens = self._tokenize(modified_norm)
        if not requested_tokens or not modified_tokens:
            return False
        if requested_tokens == modified_tokens:
            return True

        # Common short form in prompts: "dt" should match fixed_dt/max_dt/init_dt.
        if requested_norm == "dt":
            return "dt" in modified_tokens

        return False

    @staticmethod
    def _tokenize(key: str) -> list[str]:
        return [t for t in re.split(r"[._]", key) if t]
