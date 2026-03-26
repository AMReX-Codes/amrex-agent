"""
AISAC-compatible Academy wrapper for AMReX agent logic.

This is a thin wrapper around aisac_compatible_amrex_agent_code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import sys
import uuid

from academy.agent import Agent, action
from academy.exchange.cloud.client import HttpExchangeFactory
from academy.manager import Manager

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from aisac_compatible_amrex_agent_code import process_task, run_demo_workflow

EXCHANGE = "https://exchange.academy-agents.org"


class AISACCompatibleAMReXAgent(Agent):
    """[Agent] AMReX knowledge helper for simulation guidance and Q&A."""

    @action
    async def amrex_knowledge_agent(self, task: str, context: str = "{}") -> str:
        """Answer AMReX-related questions via knowledge query."""
        try:
            result = process_task(task=task, context=context)
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps(
                {
                    "answer": f"Error: {exc}",
                    "rationale": f"AMReX agent failed: {type(exc).__name__}: {exc}",
                }
            )

    @action
    async def amrex_demo_agent(self, task: str, context: str = "{}") -> str:
        """Run a dry-run remote demo workflow on Perlmutter."""
        try:
            result = run_demo_workflow(example=task, context=context)
            return json.dumps(result, default=str)
        except Exception as exc:
            return json.dumps(
                {
                    "answer": f"Error: {exc}",
                    "rationale": f"Demo workflow failed: {type(exc).__name__}: {exc}",
                }
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exchange",
        default=EXCHANGE,
        help="Academy exchange URL.",
    )
    parser.add_argument(
        "--group-id",
        default="",
        help="Optional Globus Group UUID to share the launched agent mailbox.",
    )
    return parser.parse_args()


def _resolve_group_id(group_id_arg: str) -> uuid.UUID | None:
    raw = group_id_arg.strip()
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid group id '{raw}'. Expected UUID.") from exc


async def main() -> None:
    args = _parse_args()
    group_id = _resolve_group_id(args.group_id)

    mp_ctx = multiprocessing.get_context("spawn")
    executor = ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx)
    factory = HttpExchangeFactory(args.exchange, auth_method="globus")

    async with await Manager.from_exchange_factory(
        factory=factory,
        executors=executor,
    ) as manager:
        handle = await manager.launch(AISACCompatibleAMReXAgent)
        print(f"AISACCompatibleAMReXAgent running: {handle.agent_id}")
        print(f"AISACCompatibleAMReXAgent uid: {handle.agent_id.uid}")
        if group_id is not None:
            console = await factory.console()
            try:
                await console.share_mailbox(handle.agent_id, group_id)
                print(f"Shared {handle.agent_id} with group {group_id}")
            finally:
                await console.close()
        else:
            print(
                "WARNING: No --group-id provided; "
                "agent mailbox will not be shared to a Globus group."
            )
        print("Press Ctrl+C to stop")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
