"""Metrics collection utilities for AMReXAgent."""

from __future__ import annotations

import json
import logging
import math
import time
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
_stage_start_var: ContextVar[float | None] = ContextVar("metrics_stage_start", default=None)
_node_start_var: ContextVar[float | None] = ContextVar("metrics_node_start", default=None)

DEFAULT_P95_LATENCY_TARGET_MS = 500.0
DEFAULT_MAX_CONCURRENCY = 8
POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER = "post_incident_risk_matrix_feedback"
_PRICING_PATH = Path(__file__).resolve().parents[2] / "database" / "pricing.yaml"
_DEFAULT_PRICING_TABLE: dict[str, dict[str, Any]] = {
    "gpt-4-turbo": {
        "provider": "openai",
        "input_cost_per_1k": 0.01,
        "output_cost_per_1k": 0.03,
        "currency": "USD",
    },
    "claude-3-5-sonnet-20250514": {
        "provider": "anthropic",
        "input_cost_per_1k": 0.003,
        "output_cost_per_1k": 0.015,
        "currency": "USD",
    },
}
_USER_METRIC_KEYS = (
    "user_id",
    "user",
    "username",
    "user_hash",
    "actor",
    "actor_id",
    "principal",
    "principal_id",
)


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


def normalize_metrics_event_record(
    payload: dict[str, Any],
    *,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Normalize persisted metrics records for JSONL writes."""
    normalized = dict(payload)
    existing_workflow_id = normalized.get("workflow_id")
    if not existing_workflow_id:
        normalized["workflow_id"] = workflow_id or "unknown"
    return normalized


def normalize_unnumbered_143(
    event: dict[str, Any],
    *,
    workflow_id: str | None = None,
) -> dict[str, Any]:
    """Back-compat alias for workflow-id normalization."""
    return normalize_metrics_event_record(event, workflow_id=workflow_id)


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_post_incident_feedback_records(payload: Any) -> list[dict[str, str]]:
    """Normalize post-incident risk matrix feedback payloads."""
    if payload is None:
        return []

    if isinstance(payload, dict):
        entries = [payload]
    elif isinstance(payload, list):
        entries = payload
    else:
        return []

    normalized: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        record: dict[str, str] = {}
        for key in (
            "incident_id",
            "risk_id",
            "owner",
            "update_summary",
            "mitigation_evidence_ref",
            "reviewed_at",
        ):
            text = _clean_text(entry.get(key))
            if text is not None:
                record[key] = text
        if record:
            normalized.append(record)
    return normalized


def has_post_incident_risk_matrix_feedback(payload: Any) -> bool:
    """Return True when at least one complete risk-feedback record exists."""
    required_fields = {
        "incident_id",
        "risk_id",
        "owner",
        "update_summary",
        "mitigation_evidence_ref",
        "reviewed_at",
    }
    normalized = normalize_post_incident_feedback_records(payload)
    return any(required_fields.issubset(record) for record in normalized)


def collect_post_incident_risk_matrix_feedback(state: dict[str, Any]) -> dict[str, Any]:
    """Collect normalized feedback evidence for risk-matrix updates."""
    payload = state.get(POST_INCIDENT_RISK_MATRIX_FEEDBACK_MARKER)
    if payload is None:
        payload = state.get("risk_matrix_feedback")

    feedback_records = normalize_post_incident_feedback_records(payload)
    return {
        "feedback_records": feedback_records,
        "feedback_complete": has_post_incident_risk_matrix_feedback(payload),
    }


def _append_jsonl_record(path: str, payload: dict[str, Any], *, config: Any | None = None) -> None:
    record = dict(payload)
    if config is not None:
        from src.utils.privacy import sanitize_payload

        record = sanitize_payload(record, config=config)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str))
        handle.write("\n")


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
        user: str | None = None,
    ) -> dict[str, Any] | None:
        usage = _extract_usage(response)
        if not usage:
            return None
        payload = {
            "model": model or _extract_model(response),
            "provider": provider,
            **usage,
        }
        resolved_user = _normalize_user_label(user) or _extract_user_label(_extra_var.get())
        if resolved_user is not None:
            payload["user"] = resolved_user
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
        performance_summary = _aggregate_performance(events)
        if performance_summary:
            summary["performance"] = performance_summary
        return summary

    def build_workflow_summary(self, stages: list[str] | None = None) -> dict[str, Any]:
        events = list(self._events)
        if not events:
            return {}

        if stages is None:
            stages = sorted({e.get("stage") for e in events if e.get("stage")})

        stage_summaries: dict[str, Any] = {}
        tokens_by_stage: dict[str, dict[str, int]] = {}
        cost_by_stage_usd: dict[str, float] = {}
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
                cost = llm.get("cost_usd")
                if isinstance(cost, (int, float)):
                    cost_by_stage_usd[stage] = round(float(cost), 3)

        llm_all = _aggregate_llm_usage(events)
        tokens_total_input = llm_all.get("prompt_tokens", 0)
        tokens_total_output = llm_all.get("completion_tokens", 0)
        tokens_total = llm_all.get("total_tokens", 0)
        tokens_by_user: dict[str, dict[str, int]] = {}
        for user, metrics in llm_all.get("by_user", {}).items():
            if not isinstance(metrics, dict):
                continue
            tokens_by_user[user] = {
                "input": metrics.get("prompt_tokens", 0),
                "output": metrics.get("completion_tokens", 0),
                "total": metrics.get("total_tokens", 0),
            }

        models, providers = _aggregate_models(events)

        summary = {
            "tokens_total_input": tokens_total_input,
            "tokens_total_output": tokens_total_output,
            "tokens_total": tokens_total,
            "tokens_by_stage": tokens_by_stage,
            "models": models,
            "providers": providers,
        }
        if tokens_by_user:
            summary["tokens_by_user"] = tokens_by_user
        if cost_by_stage_usd:
            summary["cost_by_stage_usd"] = cost_by_stage_usd
            summary["cost_total_usd"] = round(sum(cost_by_stage_usd.values()), 3)
        if stage_summaries:
            summary["stages"] = stage_summaries
        return summary

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def write_jsonl(self, path: str, *, config: Any | None = None) -> None:
        if not self._events:
            return
        try:
            for event in self._events:
                _append_jsonl_record(path, normalize_metrics_event_record(event), config=config)
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


def _normalize_user_label(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _extract_user_label(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    for key in _USER_METRIC_KEYS:
        normalized = _normalize_user_label(payload.get(key))
        if normalized is not None:
            return normalized
    return None


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
        "by_user": {},
        "cost_usd": 0.0,
    }
    for event in llm_events:
        data = event.get("data", {})
        model = data.get("model") or "unknown"
        user = _extract_user_label(data) or _extract_user_label(event.get("context")) or "unknown"
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
            {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
        )
        per_model["calls"] += 1
        per_model["prompt_tokens"] += prompt
        per_model["completion_tokens"] += completion
        per_model["total_tokens"] += total
        per_user = summary["by_user"].setdefault(
            user,
            {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
        )
        per_user["calls"] += 1
        per_user["prompt_tokens"] += prompt
        per_user["completion_tokens"] += completion
        per_user["total_tokens"] += total
        cost_usd, _ = _calculate_cost_usd(data)
        if isinstance(cost_usd, (int, float)):
            summary["cost_usd"] += float(cost_usd)
            per_model["cost_usd"] += float(cost_usd)
            per_user["cost_usd"] += float(cost_usd)
    for per_model in summary["by_model"].values():
        per_model["cost_usd"] = round(float(per_model["cost_usd"]), 3)
    for per_user in summary["by_user"].values():
        per_user["cost_usd"] = round(float(per_user["cost_usd"]), 3)
    summary["cost_usd"] = round(summary["cost_usd"], 3)
    return summary


def _load_pricing_table() -> dict[str, dict[str, Any]]:
    if not _PRICING_PATH.exists():
        return dict(_DEFAULT_PRICING_TABLE)

    try:
        import yaml  # type: ignore
    except Exception:
        return dict(_DEFAULT_PRICING_TABLE)

    try:
        loaded = yaml.safe_load(_PRICING_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse pricing table %s: %s", _PRICING_PATH, exc)
        return dict(_DEFAULT_PRICING_TABLE)

    if isinstance(loaded, dict):
        models = loaded.get("models")
        if isinstance(models, dict):
            merged = dict(_DEFAULT_PRICING_TABLE)
            for model_name, details in models.items():
                if isinstance(model_name, str) and isinstance(details, dict):
                    merged[model_name] = dict(details)
            return merged

    return dict(_DEFAULT_PRICING_TABLE)


def _find_pricing_model(
    model: str | None,
    provider: str | None,
    pricing_table: dict[str, dict[str, Any]],
) -> str | None:
    if model and model in pricing_table:
        return model

    if provider:
        for candidate, details in pricing_table.items():
            if isinstance(details, dict) and details.get("provider") == provider:
                return candidate

    return None


def _calculate_cost_usd(
    usage: dict[str, Any],
    *,
    pricing_table: dict[str, dict[str, Any]] | None = None,
) -> tuple[float | None, str | None]:
    table = pricing_table if pricing_table is not None else _load_pricing_table()
    model = usage.get("model")
    provider = usage.get("provider")
    pricing_model = _find_pricing_model(model, provider, table)
    if pricing_model is None:
        return None, None

    rates = table.get(pricing_model, {})
    if rates.get("currency") != "USD":
        return None, pricing_model

    input_rate = rates.get("input_cost_per_1k")
    output_rate = rates.get("output_cost_per_1k")
    if not isinstance(input_rate, (int, float)) or not isinstance(output_rate, (int, float)):
        return None, pricing_model

    prompt_tokens = usage.get("prompt_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or 0
    if not isinstance(prompt_tokens, (int, float)):
        prompt_tokens = 0
    if not isinstance(completion_tokens, (int, float)):
        completion_tokens = 0

    cost = ((float(prompt_tokens) / 1000.0) * float(input_rate)) + (
        (float(completion_tokens) / 1000.0) * float(output_rate)
    )
    return round(cost, 6), pricing_model


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


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if percentile <= 0:
        return min(values)
    if percentile >= 100:
        return max(values)
    ordered = sorted(values)
    rank = math.ceil((percentile / 100.0) * len(ordered))
    index = min(max(rank - 1, 0), len(ordered) - 1)
    return ordered[index]


def _extract_latency_ms(payload: dict[str, Any]) -> float | None:
    for field in ("latency_ms", "duration_ms", "elapsed_ms", "wall_time_ms"):
        latency = _to_float(payload.get(field))
        if latency is not None:
            return latency
    return None


def _extract_concurrency(payload: dict[str, Any]) -> int | None:
    for field in ("concurrency", "in_flight", "active_requests", "parallelism"):
        concurrency = _to_int(payload.get(field))
        if concurrency is not None:
            return concurrency
    return None


def _aggregate_performance(events: list[dict[str, Any]]) -> dict[str, Any]:
    latencies: list[float] = []
    concurrencies: list[int] = []
    latency_target = DEFAULT_P95_LATENCY_TARGET_MS
    concurrency_limit = DEFAULT_MAX_CONCURRENCY
    node_metrics: dict[str, dict[str, Any]] = {}

    for event in events:
        data = event.get("data")
        if not isinstance(data, dict):
            continue
        node = event.get("node") or "unknown"
        per_node = node_metrics.setdefault(
            node,
            {"event_count": 0, "latencies_ms": [], "concurrencies": []},
        )
        per_node["event_count"] += 1

        event_latency_target = _to_float(data.get("p95_target_ms"))
        if event_latency_target is not None:
            latency_target = min(latency_target, event_latency_target)

        event_concurrency_limit = _to_int(data.get("max_concurrency"))
        if event_concurrency_limit is not None:
            concurrency_limit = min(concurrency_limit, event_concurrency_limit)

        latency = _extract_latency_ms(data)
        if latency is not None:
            latencies.append(latency)
            per_node["latencies_ms"].append(latency)

        concurrency = _extract_concurrency(data)
        if concurrency is not None:
            concurrencies.append(concurrency)
            per_node["concurrencies"].append(concurrency)

    if not latencies and not concurrencies:
        return {}

    p95_latency_ms = _percentile(latencies, 95.0)
    max_observed_concurrency = max(concurrencies) if concurrencies else None
    summary: dict[str, Any] = {
        "p95_latency_target_ms": latency_target,
        "max_concurrency_limit": concurrency_limit,
    }
    if p95_latency_ms is not None:
        summary["p95_latency_ms"] = p95_latency_ms
        summary["p95_latency_ok"] = p95_latency_ms <= latency_target
    if max_observed_concurrency is not None:
        summary["max_observed_concurrency"] = max_observed_concurrency
        summary["concurrency_ok"] = max_observed_concurrency <= concurrency_limit

    per_node_summary: dict[str, dict[str, Any]] = {}
    for node, metrics in node_metrics.items():
        latencies_ms = metrics["latencies_ms"]
        node_p95 = _percentile(latencies_ms, 95.0) if latencies_ms else None
        node_max_concurrency = max(metrics["concurrencies"]) if metrics["concurrencies"] else None
        node_summary: dict[str, Any] = {"event_count": metrics["event_count"]}
        if node_p95 is not None:
            node_summary["p95_latency_ms"] = node_p95
            node_summary["p95_latency_ok"] = node_p95 <= latency_target
        if node_max_concurrency is not None:
            node_summary["max_observed_concurrency"] = node_max_concurrency
            node_summary["concurrency_ok"] = node_max_concurrency <= concurrency_limit
        per_node_summary[node] = node_summary
    summary["per_node"] = per_node_summary

    return summary


def normalize_average_token_fields(row: dict[str, Any]) -> dict[str, float | None]:
    """Normalize average-token summary fields to numeric-or-null values."""
    normalized: dict[str, float | None] = {}
    for field in ("avg_tokens_total", "avg_tokens_input", "avg_tokens_output"):
        value = row.get(field)
        if isinstance(value, bool):
            normalized[field] = None
        elif isinstance(value, (int, float)):
            normalized[field] = float(value)
        else:
            normalized[field] = None
    return normalized


metrics_collector = MetricsCollector()


RISK_LINK_VALIDATION_ARTIFACT = "risk_link_traceability_checker_v1"


def validate_risk_links(
    risk_links: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Validate that each risk has mitigation and validation artifact linkage.

    A missing payload is treated as valid for backwards compatibility.
    """
    if risk_links is None:
        return {
            "risk_links_valid": True,
            "risk_links_missing": [],
            "risk_links_error": None,
            "risk_links_validation_artifact": RISK_LINK_VALIDATION_ARTIFACT,
        }

    if not isinstance(risk_links, list):
        return {
            "risk_links_valid": False,
            "risk_links_missing": [],
            "risk_links_error": "risk_links must be a list[dict]",
            "risk_links_validation_artifact": RISK_LINK_VALIDATION_ARTIFACT,
        }

    missing_links: list[dict[str, Any]] = []
    for index, item in enumerate(risk_links):
        if not isinstance(item, dict):
            missing_links.append(
                {"index": index, "missing": ["risk_id", "mitigation", "validation_artifact"]}
            )
            continue

        missing_fields: list[str] = []
        risk_id = item.get("risk_id")
        mitigation = item.get("mitigation")
        validation_artifact = item.get("validation_artifact")

        if not isinstance(risk_id, str) or not risk_id.strip():
            missing_fields.append("risk_id")
        if not isinstance(mitigation, str) or not mitigation.strip():
            missing_fields.append("mitigation")
        if not isinstance(validation_artifact, str) or not validation_artifact.strip():
            missing_fields.append("validation_artifact")

        if missing_fields:
            missing_links.append({"index": index, "missing": missing_fields})

    return {
        "risk_links_valid": not missing_links,
        "risk_links_missing": missing_links,
        "risk_links_error": None if not missing_links else "risk link traceability check failed",
        "risk_links_validation_artifact": RISK_LINK_VALIDATION_ARTIFACT,
    }


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


UNNUMBERED_185_ID = "UNNUMBERED-185"
_BENCHMARK_REVIEW_KEYS = ("benchmark_reviews", "benchmark_findings", "benchmark_postmortems")
_POSTMORTEM_REVIEW_KEYS = ("postmortem_reviews", "incident_postmortems", "retrospective_reviews")
_RISK_UPDATE_KEYS = ("risk_register_updates", "new_risks", "risk_feedback_updates")


def _state_list_entries(state: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in keys:
        value = state.get(key)
        if isinstance(value, list):
            entries = [entry for entry in value if isinstance(entry, dict)]
            if entries:
                return entries
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
