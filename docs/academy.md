# Academy Integration

This page covers how AMReXAgent uses Academy and where to find upstream Academy docs.

## What this repository provides

AMReXAgent exposes an Academy-compatible wrapper in:

- `src/academy_mcp_agent.py`

The launcher used by demos is:

- `demo/mcp/academy_amrex_agent.py`

That launcher registers `AMReXMCPAgent` with the Academy exchange so external Academy/AISAC systems can invoke AMReX MCP actions.

## Minimal run example

Use your existing environment:

```bash
conda activate amrex-agent-dev
python demo/mcp/academy_amrex_agent.py
```

Expected startup:

```text
AMReXMCPAgent running: <agent_id>
Press Ctrl+C to stop
```

## Minimal Academy-side call shape

Once registered, invoke `execute_workflow` through the Academy path with payloads such as:

```json
{
  "prompt": "<your request text>",
  "steps": ["create_simulation_plan", "run_simulation"],
  "submit": {"dry_run": true}
}
```

For full MCP payload templates and field mapping, see `docs/mcp.md`.

## Upstream Academy documentation

- Academy repository (GitHub): <https://github.com/academy-agents/academy>
- Academy docs: <https://docs.academy-agents.org/latest/get-started>
- Academy package (PyPI): <https://pypi.org/project/academy-py/>
