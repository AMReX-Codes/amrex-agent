"""Metrics collection utilities for AMReXAgent."""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any, Iterator

logger = logging.getLogger(__name__)

_stage_var: ContextVar[str | None] = ContextVar("metrics_stage", default=None)
_node_var: ContextVar[str | None] = ContextVar("metrics_node", default=None)
_iteration_var: ContextVar[int | None] = ContextVar("metrics_iteration", default=None)
_extra_var: ContextVar[dict[str, Any] | None] = ContextVar("metrics_extra", default=None)
_stage_start_var: ContextVar[float | None] = ContextVar("metrics_stage_start", default=None)
_node_start_var: ContextVar[float | None] = ContextVar("metrics_node_start", default=None)


@contextmanager
def metrics_context(
    stage: str,
    *,
    node: str | None = None,
    iteration: int | None = None,
    extra: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Set metrics context for downstream instrumentation."""
    start_time = time.perf_counter()
    tokens = []
    tokens.append(_stage_var.set(stage))
    tokens.append(_stage_start_var.set(start_time))
    tokens.append(_node_start_var.set(start_time))
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

    def record_event(
        self,
        event_type: str,
        data: dict[str, Any],
        *,
        stage: str | None = None,
        node: str | None = None,
        iteration: int | None = None,
    ) -> dict[str, Any]:
        now = time.perf_counter()
        node_latency_ms = _latency_ms(_node_start_var.get(), now)
        stage_latency_ms = _latency_ms(_stage_start_var.get(), now)
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "type": event_type,
            "stage": stage or _stage_var.get() or "unknown",
            "node": node or _node_var.get() or stage or _stage_var.get() or "unknown",
            "iteration": iteration if iteration is not None else _iteration_var.get(),
            "data": data,
        }
        if node_latency_ms is not None:
            event["node_latency_ms"] = node_latency_ms
        if stage_latency_ms is not None:
            event["stage_latency_ms"] = stage_latency_ms
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
        }
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


def _latency_ms(start_time: float | None, end_time: float | None = None) -> float | None:
    if start_time is None:
        return None
    resolved_end = end_time if end_time is not None else time.perf_counter()
    return round(max(0.0, (resolved_end - start_time) * 1000.0), 3)


def _extract_model(response: Any) -> str | None:
    model = getattr(response, "model", None)
    if model:
        return model
    raw = getattr(response, "_raw_response", None)
    return getattr(raw, "model", None) if raw else None


def _aggregate_llm_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    llm_events = [e for e in events if e.get("type") == "llm_usage"]
    if not llm_events:
        return {}
    summary = {
        "total_calls": len(llm_events),
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
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
        summary["prompt_tokens"] += prompt
        summary["completion_tokens"] += completion
        summary["total_tokens"] += total
        per_model = summary["by_model"].setdefault(
            model,
            {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        per_model["calls"] += 1
        per_model["prompt_tokens"] += prompt
        per_model["completion_tokens"] += completion
        per_model["total_tokens"] += total
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


def validate_risk_owner_status_updates(
    risk_entries: Any,
    release_gate_milestones: Any,
) -> dict[str, Any]:
    """Validate risk owner/status updates are present for each release gate milestone."""
    gates = [
        str(gate).strip()
        for gate in (release_gate_milestones if isinstance(release_gate_milestones, list) else [])
        if str(gate).strip()
    ]
    if not gates:
        return {
            "passed": False,
            "failed_risks": [],
            "reason": "missing_release_gate_milestones",
        }

    if not isinstance(risk_entries, list) or not risk_entries:
        return {
            "passed": False,
            "failed_risks": [],
            "reason": "missing_risk_entries",
        }

    failed_risks: list[str] = []
    for index, entry in enumerate(risk_entries):
        if not isinstance(entry, dict):
            failed_risks.append(f"risk_{index + 1:03d}")
            continue

        risk_id = str(entry.get("risk_id") or entry.get("id") or f"risk_{index + 1:03d}")
        owner = str(entry.get("owner", "")).strip()
        updates = entry.get("status_updates")
        if not owner or not isinstance(updates, dict):
            failed_risks.append(risk_id)
            continue

        missing_gate_update = False
        for gate in gates:
            status = updates.get(gate)
            if not str(status or "").strip():
                missing_gate_update = True
                break
        if missing_gate_update:
            failed_risks.append(risk_id)

    return {
        "passed": not failed_risks,
        "failed_risks": failed_risks,
        "reason": "ok" if not failed_risks else "risk_owner_status_updates_not_met",
    }
