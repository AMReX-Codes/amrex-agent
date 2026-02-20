"""Run execute_workflow examples for plan+run and config overrides."""

import anyio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


BASELINE_JICF = "PeleLMeX/Exec/Production/JetInCrossflow"

DNS_ISOTHERMAL_PATH = "demo/pelelmex/user_requirements_DNS_isothermal.txt"
DNS_TEST_PATH = "demo/pelelmex/user_requirements_test_DNS.txt"
DNS_REACTING_PATH = "demo/pelelmex/user_requirements_DNS_isothermal_reacting.txt"


async def main() -> None:
    """Load prompt files and run execute_workflow canonical dry-run examples."""
    with open(DNS_ISOTHERMAL_PATH, "r") as handle:
        dns_isothermal_prompt = handle.read().strip()
    with open(DNS_TEST_PATH, "r") as handle:
        dns_test_prompt = handle.read().strip()
    with open(DNS_REACTING_PATH, "r") as handle:
        dns_reacting_prompt = handle.read().strip()

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

            dns_reacting = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": dns_reacting_prompt,
                    "baseline_override": BASELINE_JICF,
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "output_dir": "output/mcp/pelelmex",
                    "submit": {"dry_run": True},
                },
            )
            print(dns_reacting)

            local_override = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": dns_test_prompt,
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "config_overrides": {
                        "environment": "local",
                        "output_dir": "output/local_runs",
                    },
                    "submit": {"dry_run": True},
                },
            )
            print(local_override)

            perlmutter_override = await session.call_tool(
                "execute_workflow",
                {
                    "prompt": dns_test_prompt,
                    "steps": ["create_simulation_plan", "run_simulation"],
                    "config_overrides": {
                        "environment": "perlmutter",
                        "superfacility_account": "m1234",
                    },
                    "submit": {"dry_run": True, "nodes": 2, "walltime": "00:30:00"},
                },
            )
            print(perlmutter_override)


anyio.run(main)
