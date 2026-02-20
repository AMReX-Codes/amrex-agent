"""Register AMReXMCPAgent with the Academy exchange."""

from __future__ import annotations

import asyncio
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from academy.exchange.cloud.client import HttpExchangeFactory
from academy.manager import Manager

from src.academy_mcp_agent import AMReXMCPAgent

EXCHANGE = "https://exchange.academy-agents.org"


async def main() -> None:
    """Launch AMReXMCPAgent and wait until interrupted."""
    mp_ctx = multiprocessing.get_context("spawn")
    executor = ProcessPoolExecutor(max_workers=1, mp_context=mp_ctx)

    async with await Manager.from_exchange_factory(
        factory=HttpExchangeFactory(EXCHANGE, auth_method="globus"),
        executors=executor,
    ) as manager:
        handle = await manager.launch(AMReXMCPAgent)
        print(f"AMReXMCPAgent running: {handle.agent_id}")
        print("Press Ctrl+C to stop")
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
