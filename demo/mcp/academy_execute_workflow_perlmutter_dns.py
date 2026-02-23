"""Run a single DNS Perlmutter execute_workflow smoke call via Academy."""

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
DNS_TEST_PATH = "demo/pelelmex/user_requirements_test_DNS.txt"
DEFAULT_BASELINE = "PeleLMeX/Exec/Production/JetInCrossflow"


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
        help="Prompt file used for execute_workflow.",
    )
    parser.add_argument(
        "--output-dir",
        default="output/academy_runs/2026-02-20",
        help="Directory for writing call summaries.",
    )
    parser.add_argument(
        "--superfacility-account",
        default="m1234",
        help="Perlmutter account for config_overrides.superfacility_account.",
    )
    parser.add_argument(
        "--baseline-override",
        default=DEFAULT_BASELINE,
        help="Baseline case path for planner grounding.",
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
            final = result.get("final") or {}
            return {
                "ok": True,
                "step_names": list(steps.keys()),
                "final_keys": sorted(list(final.keys())),
                "run_directory": final.get("run_directory"),
                "job_status": final.get("job_status"),
                "script_path": final.get("script_path"),
                "selected_case": final.get("selected_case"),
            }
        return {"ok": True, "keys": sorted(list(result.keys()))}
    return {"ok": True, "type": type(result).__name__}


async def main() -> None:
    args = parse_args()
    prompt = Path(args.prompt_path).read_text().strip()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    perlmutter_dns_payload = {
        "prompt": prompt,
        "baseline_override": args.baseline_override,
        "steps": ["create_simulation_plan", "run_simulation"],
        "config_overrides": {
            "environment": "perlmutter",
            "superfacility_account": args.superfacility_account,
        },
        "submit": {"dry_run": True, "nodes": 2, "walltime": "00:30:00"},
    }

    async with await Manager.from_exchange_factory(
        factory=HttpExchangeFactory(args.exchange, auth_method="globus"),
    ) as manager:
        handle = manager.get_handle(_parse_agent_id(args.agent_id))
        result = await handle.action("execute_workflow", payload=perlmutter_dns_payload)

    report = {
        "agent_id": args.agent_id,
        "exchange": args.exchange,
        "payload_type": "dns_perlmutter_dry_run",
        "payload": perlmutter_dns_payload,
        "summary": _result_summary(result),
    }
    print(json.dumps(report, indent=2))
    (output_dir / "academy_execute_workflow_perlmutter_dns.summary.json").write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    asyncio.run(main())
