"""Smoke test AMReXMCPAgent response/rationale envelope behavior via Academy cloud."""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from academy.exchange.cloud.client import HttpExchangeFactory
from academy.identifier import AgentId
from academy.manager import Manager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-id", required=True, help="Full UUID of running AMReXMCPAgent.")
    parser.add_argument(
        "--exchange",
        default="https://exchange.academy-agents.org",
        help="Academy exchange URL.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    aid = AgentId(uid=uuid.UUID(args.agent_id.strip()))

    factory = HttpExchangeFactory(args.exchange, auth_method="globus")
    async with await Manager.from_exchange_factory(factory=factory) as manager:
        handle = manager.get_handle(aid)

        print("[1/2] create_simulation_plan with include_response_rationale=True")
        res1 = await handle.action(
            "create_simulation_plan",
            payload={
                "prompt": "Set up a reacting LES JICF case 17",
                "baseline_override": "PeleLMeX/Exec/Production/JetInCrossflow",
            },
            include_response_rationale=True,
        )
        print(json.dumps(res1, indent=2, default=str))

        print("\n[2/2] call_tool(query_knowledge) with include_response_rationale=True")
        res2 = await handle.action(
            "call_tool",
            name="query_knowledge",
            arguments={
                "question": (
                    "For PeleLMeX methane flames, how should I structure a grid refinement "
                    "study, and what chemistry mechanisms are commonly available?"
                ),
                "code": "PeleLMeX",
            },
            include_response_rationale=True,
        )
        print(json.dumps(res2, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
