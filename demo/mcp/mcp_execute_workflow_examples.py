"""Run execute_workflow examples using DNS prompt files."""

import anyio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


BASELINE_JICF = "PeleLMeX/Exec/Production/JetInCrossflow"

DNS_ISOTHERMAL_PATH = "demo/pelelmex/user_requirements_DNS_isothermal.txt"
DNS_TEST_PATH = "demo/pelelmex/user_requirements_test_DNS.txt"


async def main() -> None:
    """Load prompt files and run execute_workflow with dry-run submit."""
    # Load prompts from the demo input files.
    with open(DNS_ISOTHERMAL_PATH, "r") as handle:
        dns_isothermal_prompt = handle.read().strip()
    with open(DNS_TEST_PATH, "r") as handle:
        dns_test_prompt = handle.read().strip()

    server = StdioServerParameters(command="python", args=["-u", "mcp_server.py"])
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            dns_isothermal = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": dns_isothermal_prompt,
                    "baseline_override": BASELINE_JICF,
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "submit": {"dry_run": True},
                },
            )
            print(dns_isothermal)

            dns_test = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": dns_test_prompt,
                    "baseline_override": BASELINE_JICF,
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "submit": {"dry_run": True},
                },
            )
            print(dns_test)


anyio.run(main)
