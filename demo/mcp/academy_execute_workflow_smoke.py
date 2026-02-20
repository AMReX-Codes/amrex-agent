"""Call AMReXMCPAgent actions over Academy exchange for smoke validation."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
import uuid

from academy.exchange.cloud.client import HttpExchangeFactory
from academy.identifier import AgentId
from academy.manager import Manager

EXCHANGE = "https://exchange.academy-agents.org"
BASELINE_JICF = "PeleLMeX/Exec/Production/JetInCrossflow"

DNS_TEST_PATH = "demo/pelelmex/user_requirements_test_DNS.txt"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-id", required=True, help="Academy agent ID to call.")
    parser.add_argument(
        "--exchange",
        default=EXCHANGE,
        help="Academy exchange URL.",
    )
    parser.add_argument(
        "--prompt-path",
        default=DNS_TEST_PATH,
        help="Prompt file used for execute_workflow calls.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/handoff_runs/2026-02-20",
        help="Directory for writing call summaries.",
    )
    return parser.parse_args()


def _parse_agent_id(agent_id_arg: str) -> AgentId:
    """
    Parse full UUID agent id into academy AgentId.

    The short repr form (for example ``AgentId<70545964>``) is not reversible.
    """
    value = agent_id_arg.strip()
    if value.startswith("AgentId<") and value.endswith(">"):
        inner = value[len("AgentId<") : -1]
        raise ValueError(
            "Received short AgentId repr "
            f"'{value}'. Use full UUID instead (for example from "
            "'AMReXMCPAgent uid: <uuid>')."
        )
    try:
        uid = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid --agent-id '{agent_id_arg}'. Expected full UUID."
        ) from exc
    return AgentId(uid=uid)


def _result_summary(result: Any) -> dict[str, Any]:
    """Return compact response summary for stable logging."""
    if isinstance(result, dict):
        if "error" in result:
            return {"ok": False, "error": str(result.get("error"))}
        steps = result.get("steps")
        if isinstance(steps, dict):
            return {
                "ok": True,
                "step_names": list(steps.keys()),
                "final_keys": sorted(list((result.get("final") or {}).keys())),
            }
        return {"ok": True, "keys": sorted(list(result.keys()))}
    return {"ok": True, "type": type(result).__name__}


async def main() -> None:
    args = parse_args()
    prompt = Path(args.prompt_path).read_text().strip()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    plan_run_payload = {
        "prompt": prompt,
        "baseline_override": BASELINE_JICF,
        "steps": ["create_simulation_plan", "run_simulation"],
        "submit": {"dry_run": True},
    }
    config_override_payload = {
        "prompt": prompt,
        "steps": ["create_simulation_plan", "run_simulation"],
        "config_overrides": {
            "environment": "local",
            "output_dir": "output/local_runs",
        },
        "submit": {"dry_run": True},
    }
    visualization_payload = {
        "run_directory": "output/mcp/pelelmex/run_001",
    }

    calls: list[dict[str, Any]] = []

    async with await Manager.from_exchange_factory(
        factory=HttpExchangeFactory(args.exchange, auth_method="globus"),
    ) as manager:
        handle = manager.get_handle(_parse_agent_id(args.agent_id))

        tools = await handle.action("list_tools")
        calls.append(
            {
                "action": "list_tools",
                "summary": _result_summary(tools),
            }
        )

        plan_run = await handle.action("execute_workflow", payload=plan_run_payload)
        calls.append(
            {
                "action": "execute_workflow",
                "payload_type": "plan_run",
                "summary": _result_summary(plan_run),
            }
        )

        override_run = await handle.action("execute_workflow", payload=config_override_payload)
        calls.append(
            {
                "action": "execute_workflow",
                "payload_type": "config_override",
                "summary": _result_summary(override_run),
            }
        )

        viz = await handle.action(
            "call_tool",
            name="generate_visualizations",
            arguments=visualization_payload,
        )
        calls.append(
            {
                "action": "call_tool",
                "tool": "generate_visualizations",
                "summary": _result_summary(viz),
            }
        )

    report = {
        "agent_id": args.agent_id,
        "exchange": args.exchange,
        "calls": calls,
    }
    print(json.dumps(report, indent=2))
    (output_dir / "academy_execute_workflow_smoke.summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
