"""Metrics collection utilities for AMReXAgent."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_stage_var: ContextVar[str | None] = ContextVar("metrics_stage", default=None)
_node_var: ContextVar[str | None] = ContextVar("metrics_node", default=None)
_iteration_var: ContextVar[int | None] = ContextVar("metrics_iteration", default=None)
_extra_var: ContextVar[dict[str, Any] | None] = ContextVar("metrics_extra", default=None)

_DEFAULT_PRICING_TABLE: dict[str, dict[str, Any]] = {
    "claude-3-5-sonnet-20250514": {
        "provider": "anthropic",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "currency": "USD",
    },
    "llama-3.1-70b-instruct": {
        "provider": "alcf",
        "input_cost_per_1k": 0.0005,
        "output_cost_per_1k": 0.001,
        "currency": "USD",
    },
    "gpt-4-turbo": {
        "provider": "openai",
        "input_cost_per_1k": 0.01,
        "output_cost_per_1k": 0.03,
        "currency": "USD",
    },
}
_PRICING_PATH = Path(__file__).resolve().parents[1] / "config" / "pricing.yaml"


@contextmanager
def metrics_context(
    stage: str,
    *,
    node: str | None = None,
    iteration: int | None = None,
    extra: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Set metrics context for downstream instrumentation."""
    tokens = []
    tokens.append(_stage_var.set(stage))
    if node is not None:
        tokens.append(_node_var.set(node))
    if iteration is not None:
        tokens.append(_iteration_var.set(iteration))
    if extra is not None:
        tokens.append(_extra_var.set(extra))
    try:
        yield
    finally:
        for token in reversed(tokens):
            token.var.reset(token)


@contextmanager
def metrics_extra(extra: dict[str, Any] | None) -> Iterator[None]:
    """Set metrics context extra fields without changing stage."""
    if extra is None:
        yield
        return
    token = _extra_var.set(extra)
    try:
        yield
    finally:
        _extra_var.reset(token)


class MetricsCollector:
    """Collects instrumentation events for aggregation and export."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._pricing_table = _load_pricing_table()

    def record_event(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        stage: str | None = None,
        node: str | None = None,
        iteration: int | None = None,
    ) -> dict[str, Any]:
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": event_type,
            "stage": stage or _stage_var.get() or "unknown",
            "node": node or _node_var.get() or stage or _stage_var.get() or "unknown",
            "iteration": iteration if iteration is not None else _iteration_var.get(),
            "data": data,
        }
        extra = _extra_var.get()
        if extra:
            event["context"] = dict(extra)
        self._events.append(event)
        return event

    def record_llm_usage(
        self,
        response: Any,
        *,
        model: str | None = None,
        provider: str | None = None,
    ) -> dict[str, Any] | None:
        usage = _extract_usage(response)
        if not usage:
            return None
        payload = {
            "model": model or _extract_model(response),
            "provider": provider,
            **usage,
        }
        cost_usd, pricing_model = _calculate_cost_usd(payload, pricing_table=self._pricing_table)
        if cost_usd is not None:
            payload["cost_usd"] = cost_usd
        if pricing_model is not None:
            payload["pricing_model"] = pricing_model
        return self.record_event("llm_usage", payload)

    def summarize_stage(self, stage: str, iteration: int | None = None) -> dict[str, Any]:
        events = [
            e
            for e in self._events
            if e.get("stage") == stage and (iteration is None or e.get("iteration") == iteration)
        ]
        if not events:
            return {}

        summary: dict[str, Any] = {}
        llm_summary = _aggregate_llm_usage(events)
        if llm_summary:
            summary["llm"] = llm_summary
        retrieval_summary = _aggregate_retrieval(events)
        if retrieval_summary:
            summary["retrieval"] = retrieval_summary
        validation_summary = _aggregate_validation(events)
        if validation_summary:
            summary["validation"] = validation_summary
        return summary

    def build_workflow_summary(self, stages: list[str] | None = None) -> dict[str, Any]:
        events = list(self._events)
        if not events:
            return {}

        if stages is None:
            stages = sorted({e.get("stage") for e in events if e.get("stage")})

        stage_summaries: dict[str, Any] = {}
        tokens_by_stage: dict[str, dict[str, int]] = {}
        for stage in stages:
            summary = self.summarize_stage(stage)
            if summary:
                stage_summaries[stage] = summary
            llm = summary.get("llm", {})
            if llm:
                tokens_by_stage[stage] = {
                    "input": llm.get("prompt_tokens", 0),
                    "output": llm.get("completion_tokens", 0),
                    "total": llm.get("total_tokens", 0),
                }

        llm_all = _aggregate_llm_usage(events)
        tokens_total_input = llm_all.get("prompt_tokens", 0)
        tokens_total_output = llm_all.get("completion_tokens", 0)
        tokens_total = llm_all.get("total_tokens", 0)

        models, providers = _aggregate_models(events)

        summary = {
            "tokens_total_input": tokens_total_input,
            "tokens_total_output": tokens_total_output,
            "tokens_total": tokens_total,
            "tokens_by_stage": tokens_by_stage,
            "models": models,
            "providers": providers,
            "cost_total_usd": llm_all.get("cost_usd", 0.0),
        }
        cost_by_stage_usd = {
            stage: stage_summary.get("llm", {}).get("cost_usd", 0.0)
            for stage, stage_summary in stage_summaries.items()
            if stage_summary.get("llm")
        }
        if cost_by_stage_usd:
            summary["cost_by_stage_usd"] = cost_by_stage_usd
        if stage_summaries:
            summary["stages"] = stage_summaries
        return summary

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def write_jsonl(self, path: str, *, config: Any | None = None) -> None:
        if not self._events:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                for event in self._events:
                    payload = event
                    if config is not None:
                        from src.utils.privacy import sanitize_payload

                        payload = sanitize_payload(event, config=config)
                    handle.write(json.dumps(payload, default=str))
                    handle.write("\n")
        except Exception as exc:
            logger.warning("Failed to write metrics JSONL to %s: %s", path, exc)

    def reset(self) -> None:
        self._events = []


def _extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    if usage is None:
        usage = getattr(getattr(response, "_raw_response", None), "usage", None)
    if usage is None:
        usage = getattr(getattr(response, "response", None), "usage", None)
    if usage is None:
        return {}
    if isinstance(usage, dict):
        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
        completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")
    else:
        prompt_tokens = getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

    if total_tokens is None and (prompt_tokens is not None or completion_tokens is not None):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)

    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return {}

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _extract_model(response: Any) -> str | None:
    model = getattr(response, "model", None)
    if model:
        return model
    raw = getattr(response, "_raw_response", None)
    return getattr(raw, "model", None) if raw else None


def _load_pricing_table() -> dict[str, dict[str, Any]]:
    table = {name: dict(values) for name, values in _DEFAULT_PRICING_TABLE.items()}
    if not _PRICING_PATH.exists():
        return table
    try:
        import yaml

        loaded = yaml.safe_load(_PRICING_PATH.read_text(encoding="utf-8")) or {}
        models = loaded.get("models")
        if isinstance(models, dict):
            for model, config in models.items():
                if isinstance(config, dict):
                    table[model] = dict(config)
    except Exception as exc:
        logger.warning("Failed to load pricing config from %s: %s", _PRICING_PATH, exc)
    return table


def _find_pricing_model(
    model: str | None,
    provider: str | None,
    pricing_table: dict[str, dict[str, Any]],
) -> str | None:
    if model and model in pricing_table:
        return model
    if not provider:
        return None
    for model_name, model_pricing in pricing_table.items():
        if model_pricing.get("provider") == provider:
            return model_name
    return None


def _calculate_cost_usd(
    usage: dict[str, Any],
    *,
    pricing_table: dict[str, dict[str, Any]],
) -> tuple[float | None, str | None]:
    pricing_model = _find_pricing_model(usage.get("model"), usage.get("provider"), pricing_table)
    if not pricing_model:
        return None, None

    pricing = pricing_table.get(pricing_model, {})
    if pricing.get("currency", "USD") != "USD":
        return None, pricing_model

    input_rate = pricing.get("input_cost_per_1k")
    output_rate = pricing.get("output_cost_per_1k")
    if input_rate is None or output_rate is None:
        return None, pricing_model

    prompt_tokens = usage.get("prompt_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or 0
    cost = (prompt_tokens / 1000) * float(input_rate) + (completion_tokens / 1000) * float(output_rate)
    return round(cost, 8), pricing_model


def _aggregate_llm_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    llm_events = [e for e in events if e.get("type") == "llm_usage"]
    if not llm_events:
        return {}
    summary = {
        "total_calls": len(llm_events),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
        "by_model": {},
    }
    for event in llm_events:
        data = event.get("data", {})
        model = data.get("model") or "unknown"
        prompt = data.get("prompt_tokens") or 0
        completion = data.get("completion_tokens") or 0
        total = data.get("total_tokens")
        if total is None:
            total = prompt + completion
        cost_usd = data.get("cost_usd")
        if cost_usd is None:
            cost_usd, _ = _calculate_cost_usd(data, pricing_table=_DEFAULT_PRICING_TABLE)
        if cost_usd is None:
            cost_usd = 0.0
        summary["prompt_tokens"] += prompt
        summary["completion_tokens"] += completion
        summary["total_tokens"] += total
        summary["cost_usd"] += cost_usd
        per_model = summary["by_model"].setdefault(
            model,
            {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
        )
        per_model["calls"] += 1
        per_model["prompt_tokens"] += prompt
        per_model["completion_tokens"] += completion
        per_model["total_tokens"] += total
        per_model["cost_usd"] += cost_usd
    summary["cost_usd"] = round(summary["cost_usd"], 8)
    for per_model in summary["by_model"].values():
        per_model["cost_usd"] = round(per_model["cost_usd"], 8)
    return summary


def _aggregate_retrieval(events: list[dict[str, Any]]) -> dict[str, Any]:
    retrieval_events = [e for e in events if e.get("type") == "retrieval_strategy"]
    if not retrieval_events:
        return {}
    summary: dict[str, Any] = {"strategies": {}, "last": None}
    for event in retrieval_events:
        data = event.get("data", {})
        strategy = data.get("strategy") or "unknown"
        summary["strategies"][strategy] = summary["strategies"].get(strategy, 0) + 1
        summary["last"] = data
    return summary


def _aggregate_validation(events: list[dict[str, Any]]) -> dict[str, Any]:
    validation_events = [e for e in events if e.get("type") == "validation_metrics"]
    if not validation_events:
        return {}
    return validation_events[-1].get("data", {})


def _aggregate_models(events: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    models: list[str] = []
    providers: list[str] = []
    for event in events:
        if event.get("type") != "llm_usage":
            continue
        data = event.get("data", {})
        model = data.get("model")
        provider = data.get("provider")
        if model and model not in models:
            models.append(model)
        if provider and provider not in providers:
            providers.append(provider)
    return models, providers


metrics_collector = MetricsCollector()


UNNUMBERED_185_ID = "UNNUMBERED-185"
_BENCHMARK_REVIEW_KEYS = ("benchmark_reviews", "benchmark_findings", "benchmark_postmortems")
_POSTMORTEM_REVIEW_KEYS = ("postmortem_reviews", "incident_postmortems", "retrospective_reviews")
_RISK_UPDATE_KEYS = ("risk_register_updates", "new_risks", "risk_feedback_updates")


def _state_list_entries(state: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in keys:
        value = state.get(key)
        if isinstance(value, list):
            return [entry for entry in value if isinstance(entry, dict)]
    return []


def _normalized_risk_id(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


def _extract_review_risk_ids(entries: list[dict[str, Any]]) -> set[str]:
    risk_ids: set[str] = set()
    for entry in entries:
        for key in ("risk_id", "risk", "id"):
            normalized = _normalized_risk_id(entry.get(key))
            if normalized:
                risk_ids.add(normalized)
                break
    return risk_ids


def _extract_update_risk_ids(entries: list[dict[str, Any]]) -> set[str]:
    risk_ids: set[str] = set()
    for entry in entries:
        normalized = _normalized_risk_id(entry.get("risk_id"))
        if normalized:
            risk_ids.add(normalized)
            continue

        risks = entry.get("risks")
        if isinstance(risks, list):
            for item in risks:
                normalized = _normalized_risk_id(item)
                if normalized:
                    risk_ids.add(normalized)
    return risk_ids


def benchmark_postmortem_risk_feedback_passed(state: dict[str, Any]) -> bool:
    gate_approvals = state.get("gate_approvals", [])
    if isinstance(gate_approvals, list):
        for approval in gate_approvals:
            if not isinstance(approval, dict):
                continue
            if approval.get("decision") != "approved":
                continue
            details = approval.get("details", {})
            if isinstance(details, dict) and details.get("criterion") == UNNUMBERED_185_ID:
                return True

    benchmark_reviews = _state_list_entries(state, _BENCHMARK_REVIEW_KEYS)
    if not benchmark_reviews:
        return False

    postmortem_reviews = _state_list_entries(state, _POSTMORTEM_REVIEW_KEYS)
    if not postmortem_reviews:
        return False

    review_risk_ids = _extract_review_risk_ids(benchmark_reviews)
    review_risk_ids.update(_extract_review_risk_ids(postmortem_reviews))
    if not review_risk_ids:
        return False

    risk_updates = _state_list_entries(state, _RISK_UPDATE_KEYS)
    if not risk_updates:
        return False

    updated_risk_ids = _extract_update_risk_ids(risk_updates)
    if not updated_risk_ids:
        return False

    return review_risk_ids.issubset(updated_risk_ids)


def benchmark_postmortem_risk_feedback_failure_reason(state: dict[str, Any]) -> str:
    if benchmark_postmortem_risk_feedback_passed(state):
        return "benchmark_postmortem_risk_feedback_satisfied"

    benchmark_reviews = _state_list_entries(state, _BENCHMARK_REVIEW_KEYS)
    if not benchmark_reviews:
        return "benchmark_reviews_missing"

    postmortem_reviews = _state_list_entries(state, _POSTMORTEM_REVIEW_KEYS)
    if not postmortem_reviews:
        return "postmortem_reviews_missing"

    review_risk_ids = _extract_review_risk_ids(benchmark_reviews)
    review_risk_ids.update(_extract_review_risk_ids(postmortem_reviews))
    if not review_risk_ids:
        return "review_risks_missing"

    risk_updates = _state_list_entries(state, _RISK_UPDATE_KEYS)
    if not risk_updates:
        return "risk_updates_missing"

    updated_risk_ids = _extract_update_risk_ids(risk_updates)
    if not updated_risk_ids:
        return "risk_updates_missing"

    return "risk_updates_incomplete"
