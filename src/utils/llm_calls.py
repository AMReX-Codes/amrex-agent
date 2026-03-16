"""Shared LLM call helper with policy hooks and instructor fallback."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.utils.metrics import metrics_extra


@dataclass(frozen=True)
class LLMCallSpec:
    model: str
    messages: list[dict[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    response_model: Any | None = None
    response_format: dict[str, Any] | None = None
    max_retries: int | None = None
    purpose: str | None = None
    template_name: str | None = None
    template_source: str | None = None


class LLMPolicy:
    """Policy interface for governed LLM calls."""

    def check_budget(self, _spec: LLMCallSpec) -> tuple[bool, str | None]:
        return True, None

    def check_rate_limit(self, _spec: LLMCallSpec) -> tuple[bool, str | None]:
        return True, None

    def check_approval(self, _spec: LLMCallSpec) -> tuple[bool, str | None]:
        return True, None

    def audit(self, _event: str, _spec: LLMCallSpec, _details: dict[str, Any]) -> None:
        return None


class PolicyViolation(RuntimeError):
    pass


def call_llm(
    client: Any,
    spec: LLMCallSpec,
    *,
    config: Any | None = None,
    policy: LLMPolicy | None = None,
    extra_context: dict[str, Any] | None = None,
    fallback_parser: Callable[[Any], Any] | None = None,
) -> Any:
    if config is not None:
        from src.utils.privacy import enforce_strict

        for message in spec.messages:
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, str):
                enforce_strict(content, config=config, purpose="llm_call")

    policy = policy or LLMPolicy()
    ok, reason = policy.check_rate_limit(spec)
    if not ok:
        policy.audit("llm_denied", spec, {"reason": reason, "type": "rate_limit"})
        raise PolicyViolation(reason or "rate_limit")
    ok, reason = policy.check_budget(spec)
    if not ok:
        policy.audit("llm_denied", spec, {"reason": reason, "type": "budget"})
        raise PolicyViolation(reason or "budget")
    ok, reason = policy.check_approval(spec)
    if not ok:
        policy.audit("llm_denied", spec, {"reason": reason, "type": "approval"})
        raise PolicyViolation(reason or "approval")

    with metrics_extra(extra_context):
        policy.audit("llm_allowed", spec, {})
        if spec.response_model:
            try:
                import instructor
                from src.config import unwrap_llm_client, wrap_llm_client

                base_client = unwrap_llm_client(client)
                instr_client = instructor.from_openai(base_client)
                instr_client = wrap_llm_client(instr_client, config or {})
                create_kwargs: dict[str, Any] = {
                    "model": spec.model,
                    "response_model": spec.response_model,
                    "messages": spec.messages,
                    "temperature": spec.temperature,
                }
                # Instructor/tenacity expects an int or Retrying object; avoid passing None.
                if spec.max_retries is not None:
                    create_kwargs["max_retries"] = spec.max_retries
                return instr_client.chat.completions.create(**create_kwargs)
            except (ImportError, ModuleNotFoundError):
                pass

        response = client.chat.completions.create(
            model=spec.model,
            messages=spec.messages,
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
            response_format=spec.response_format,
        )
        if fallback_parser:
            return fallback_parser(response)
        return response
