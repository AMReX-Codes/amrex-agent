"""Register AMReXMCPAgent with the Academy exchange."""

from __future__ import annotations

import argparse
import asyncio
import multiprocessing
import sys
import uuid
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from academy.exchange.cloud.client import HttpExchangeFactory
from academy.manager import Manager

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.academy_mcp_agent import AMReXMCPAgent

EXCHANGE = "https://exchange.academy-agents.org"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exchange",
        default=EXCHANGE,
        help="Academy exchange URL.",
    )
    parser.add_argument(
        "--group-id",
        default="",
        help=(
            "Optional Globus Group UUID to share the launched agent mailbox."
        ),
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
    """Launch AMReXMCPAgent and wait until interrupted."""
    args = parse_args()
    group_id = _resolve_group_id(args.group_id)

    mp_ctx = multiprocessing.get_context("spawn")
    executor = ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx)
    factory = HttpExchangeFactory(args.exchange, auth_method="globus")

    async with await Manager.from_exchange_factory(
        factory=factory,
        executors=executor,
    ) as manager:
        handle = await manager.launch(AMReXMCPAgent)
        print(f"AMReXMCPAgent running: {handle.agent_id}")
        print(f"AMReXMCPAgent uid: {handle.agent_id.uid}")
        if group_id is not None:
            console = await factory.console()
            try:
                await console.share_mailbox(handle.agent_id, group_id)
                print(f"Shared {handle.agent_id} with group {group_id}")
            finally:
                await console.close()
        else:
            print("WARNING: No --group-id provided; agent mailbox will not be shared to a Globus group.")
        print("Press Ctrl+C to stop")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
