from __future__ import annotations

from typing import Any


def _match_expected(value: str, row: dict[str, Any], exact_key: str, prefix_key: str) -> bool:
    expected_exact = str(row.get(exact_key, "") or "").strip()
    expected_prefix = str(row.get(prefix_key, "") or "").strip()
    if expected_exact:
        return value == expected_exact
    if expected_prefix:
        return value.startswith(expected_prefix)
    return False


def _stage_correctness(stage: str, row: dict[str, Any], selected: dict[str, str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if stage == "architect":
        solver_expected = str(row.get("expected_solver", "ERF") or "ERF")
        solver_ok = selected.get("selected_solver", "") == solver_expected
        case_ok = _match_expected(
            selected.get("selected_case", ""),
            row,
            "target_case_relpath",
            "expected_case_prefix",
        )
        if not solver_ok:
            reasons.append("solver_mismatch")
        if not case_ok:
            reasons.append("case_mismatch")
        return (1.0 if solver_ok and case_ok else 0.0), reasons
    if stage == "input_writer":
        inputs_ok = _match_expected(
            selected.get("selected_inputs", ""),
            row,
            "target_inputs_relpath",
            "expected_inputs_prefix",
        )
        if not inputs_ok:
            reasons.append("inputs_mismatch")
        return (1.0 if inputs_ok else 0.0), reasons
    return 1.0, reasons


def _generalizability_score(
    row: dict[str, Any],
    row_events: list[dict[str, str]],
    unavailable: bool,
) -> tuple[float, list[str]]:
    score = 1.0
    reasons: list[str] = []
    warning_count = sum(1 for event in row_events if event.get("severity") == "warning")
    error_count = sum(1 for event in row_events if event.get("severity") != "warning")
    if warning_count:
        score -= 0.2
        reasons.append("warn_signal")
    if error_count:
        score -= 0.4
        reasons.append("error_signal")
    if unavailable:
        score -= 0.5
        reasons.append("llm_unavailable")
    prompt_text = str(row.get("prompt_text", "") or "").lower()
    case_hint = str(row.get("target_case_relpath", "") or "").lower()
    if case_hint and case_hint.lower() in prompt_text:
        score -= 0.2
        reasons.append("literal_case_in_prompt")
    return max(0.0, round(score, 6)), reasons


def _selected_payload_fields(payload: dict[str, Any], selected_case: str, selected_inputs: str) -> dict[str, str]:
    plan = payload.get("plan", {}) if isinstance(payload.get("plan"), dict) else {}
    solver = str(plan.get("selected_solver") or payload.get("selected_solver") or "").strip()
    return {
        "selected_solver": solver,
        "selected_case": selected_case,
        "selected_inputs": selected_inputs,
    }


def build_call_records(
    *,
    row: dict[str, Any],
    strategy: str,
    payload: dict[str, Any],
    llm_usage_events: list[dict[str, Any]],
    selected_case: str,
    selected_inputs: str,
    row_events: list[dict[str, str]],
    unavailable: bool,
) -> list[dict[str, Any]]:
    selected = _selected_payload_fields(payload, selected_case, selected_inputs)
    records: list[dict[str, Any]] = []
    for event in llm_usage_events:
        stage = str(event.get("stage") or "")
        correctness, correctness_reasons = _stage_correctness(stage, row, selected)
        generalizability, generalizability_reasons = _generalizability_score(row, row_events, unavailable)
        explainability = round((0.7 * correctness) + (0.3 * generalizability), 6)
        fail_reasons = correctness_reasons + generalizability_reasons
        data = event.get("data", {}) if isinstance(event.get("data"), dict) else {}
        records.append(
            {
                "row_id": row.get("row_id"),
                "prompt_family": row.get("prompt_family"),
                "strategy": strategy,
                "stage": stage,
                "purpose": "solver_baseline_selection" if stage == "architect" else "inputs_selection",
                "template_name": None,
                "template_source": None,
                "expected_contract": {
                    "expected_solver": row.get("expected_solver", "ERF"),
                    "target_case_relpath": row.get("target_case_relpath"),
                    "expected_case_prefix": row.get("expected_case_prefix"),
                    "target_inputs_relpath": row.get("target_inputs_relpath"),
                    "expected_inputs_prefix": row.get("expected_inputs_prefix"),
                },
                "observed": selected,
                "correctness_score": correctness,
                "generalizability_score": generalizability,
                "explainability_score": explainability,
                "fail_reasons": fail_reasons,
                "llm_model": data.get("model"),
                "llm_provider": data.get("provider"),
                "prompt_tokens": data.get("prompt_tokens"),
                "completion_tokens": data.get("completion_tokens"),
            }
        )
    return records


def summarize_explainability(records: list[dict[str, Any]], threshold: float = 0.9) -> dict[str, Any]:
    if not records:
        return {
            "explainability_pass": False,
            "explainability_mean_score": 0.0,
            "correctness_mean_score": 0.0,
            "generalizability_mean_score": 0.0,
            "explainability_fail_count": 0,
        }
    n = len(records)
    explainability_mean = round(sum(float(r.get("explainability_score", 0.0)) for r in records) / n, 6)
    correctness_mean = round(sum(float(r.get("correctness_score", 0.0)) for r in records) / n, 6)
    generalizability_mean = round(sum(float(r.get("generalizability_score", 0.0)) for r in records) / n, 6)
    fail_count = sum(1 for r in records if float(r.get("correctness_score", 0.0)) < 1.0)
    return {
        "explainability_pass": explainability_mean >= threshold and fail_count == 0,
        "explainability_mean_score": explainability_mean,
        "correctness_mean_score": correctness_mean,
        "generalizability_mean_score": generalizability_mean,
        "explainability_fail_count": fail_count,
    }
