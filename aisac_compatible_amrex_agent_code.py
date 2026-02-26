"""AISAC-compatible AMReX logic for knowledge and demo actions."""

from __future__ import annotations

import json
from typing import Any

from src.interactive_service import invoke_tool


DEFAULT_SOLVER = "PeleLMeX"
DEFAULT_BASELINE_OVERRIDE = "PeleLMeX/Exec/Production/JetInCrossflow"


def _parse_context(context: str | dict[str, Any] | None) -> dict[str, Any]:
    if context is None:
        return {}
    if isinstance(context, dict):
        return dict(context)
    raw = context.strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def process_task(task: str, context: str | dict[str, Any] | None = "{}") -> dict[str, Any]:
    """
    Run a knowledge query and return AISAC-friendly response fields.

    Inputs:
    - task: user question
    - context (optional JSON/dict): may include "code" to select solver
    """
    context_dict = _parse_context(context)
    payload: dict[str, Any] = {"question": task}
    solver = (
        context_dict.get("selected_solver")
        or context_dict.get("code_name")
        or context_dict.get("code")
        or DEFAULT_SOLVER
    )
    payload["code"] = solver

    result = invoke_tool(
        "query_knowledge",
        payload,
        surface="aisac",
        caller_action="amrex_knowledge_agent",
    )
    base_answer = str(result.get("answer", "No answer available"))
    method = result.get("method", "unknown")
    confidence = result.get("confidence", 0.0)
    sources = result.get("sources", [])
    sources_list = [str(src) for src in sources] if sources else []
    source_lines = (
        "\n".join(f"- `{src}`" for src in sources_list)
        if sources_list
        else "- None provided"
    )
    answer = (
        "# AMReX Knowledge Response\n\n"
        "## Answer\n\n"
        f"{base_answer}\n\n"
        "## Metadata\n\n"
        f"- Solver: `{solver}`\n"
        f"- Method: `{method}`\n"
        f"- Confidence: `{confidence}`\n\n"
        "## Sources\n\n"
        f"{source_lines}"
    )
    rationale = "Answered via mcp_query_knowledge."

    return {
        "answer": answer,
        "rationale": rationale,
    }


def run_demo_workflow(
    example: str,
    context: str | dict[str, Any] | None = "{}",
) -> dict[str, Any]:
    """Run a constrained demo workflow on Perlmutter in dry-run mode."""
    context_dict = _parse_context(context)
    key = (context_dict.get("example") or "ad_hoc").strip()

    prompt = context_dict.get("prompt")
    if not prompt:
        prompt = (example or "").strip()
    if not prompt:
        raise ValueError("Missing prompt. Provide text as first argument or context.prompt.")

    baseline_override = context_dict.get("baseline_override") or DEFAULT_BASELINE_OVERRIDE

    payload: dict[str, Any] = {
        "prompt": prompt,
        "baseline_override": baseline_override,
        "steps": ["create_simulation_plan", "run_simulation"],
        "submit": {
            "system": "perlmutter",
            "dry_run": True,
        },
        "config_overrides": {
            "environment": "perlmutter",
            "run_mode": "dry",
            "dry_run": True,
        },
    }

    result = invoke_tool(
        "execute_workflow",
        payload,
        surface="aisac",
        caller_action="amrex_demo_agent",
    )
    final = result.get("final", {}) if isinstance(result, dict) else {}
    run_dir = final.get("run_directory")
    job_status = final.get("job_status")
    selected_case = final.get("selected_case")

    answer = (
        "# AMReX Demo Workflow Result\n\n"
        "## Summary\n\n"
        "Executed constrained demo workflow in dry-run mode on Perlmutter.\n\n"
        "## Run Details\n\n"
        f"- Example: `{key}`\n"
        f"- Selected Case: `{selected_case}`\n"
        f"- Job Status: `{job_status}`\n"
        f"- Run Directory: `{run_dir}`\n"
        f"- Baseline Override: `{baseline_override}`\n"
        "- Steps: `create_simulation_plan`, `run_simulation`\n"
    )

    return {
        "answer": answer,
        "rationale": (
            "Ran execute_workflow with steps=create_simulation_plan+run_simulation "
            "using dry-run Perlmutter settings."
        ),
    }
