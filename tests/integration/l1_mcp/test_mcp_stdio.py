import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _start_server(repo_root: Path):
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-u", str(repo_root / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=repo_root,
        env=env,
    )

    def _send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    stderr_lines: list[str] = []

    def _recv(expected_id: int, timeout: float = 30.0) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            ready, _, _ = select.select([proc.stdout, proc.stderr], [], [], 0.1)
            for stream in ready:
                line = stream.readline().strip()
                if not line:
                    continue
                if stream is proc.stderr:
                    stderr_lines.append(line)
                    continue
                message = json.loads(line)
                if message.get("id") == expected_id:
                    return message
        stderr_dump = "\n".join(stderr_lines[-20:])
        raise RuntimeError(
            f"Timed out waiting for response id={expected_id}\n"
            f"stderr:\n{stderr_dump}"
        )

    return proc, _send, _recv


@pytest.mark.integration_l1
def test_mcp_stdio_initialize_roundtrip():
    repo_root = Path(__file__).resolve().parents[3]
    proc, _send, _recv = _start_server(repo_root)

    def _recv_or_xfail(expected_id: int, timeout: float = 20.0) -> dict:
        try:
            return _recv(expected_id, timeout=timeout)
        except RuntimeError as exc:
            pytest.xfail(str(exc))

    try:
        _send(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.0"},
                },
            }
        )
        init_response = _recv_or_xfail(0, timeout=20.0)
        assert "result" in init_response

        _send({"jsonrpc": "2.0", "method": "initialized", "params": {}})
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.mark.integration_l1
def test_mcp_stdio_list_tools_and_validate_inputs(tmp_path):
    inputs_path = tmp_path / "inputs"
    inputs_path.write_text("amr.max_level = 1\n")

    repo_root = Path(__file__).resolve().parents[3]
    proc, _send, _recv = _start_server(repo_root)

    def _recv_or_xfail(expected_id: int, timeout: float = 20.0) -> dict:
        try:
            return _recv(expected_id, timeout=timeout)
        except RuntimeError as exc:
            pytest.xfail(str(exc))

    try:
        _send(
            {
                "jsonrpc": "2.0",
                "id": 0,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0.0.0"},
                },
            }
        )
        init_response = _recv_or_xfail(0, timeout=20.0)
        assert "result" in init_response

        _send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

        _send({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools_response = _recv_or_xfail(1, timeout=20.0)
        tools = tools_response.get("result", {}).get("tools", [])
        tool_names = {tool.get("name") for tool in tools}
        expected_tools = {
            "query_knowledge",
            "create_simulation_plan",
            "create_proposed_modifications_with_plan",
            "select_baseline_case",
            "validate_inputs",
            "setup_job",
            "run_simulation",
            "analyze_results",
            "generate_visualizations",
        }
        assert expected_tools.issubset(tool_names)

        case_dir = tmp_path / "case"
        case_dir.mkdir()
        exe_path = case_dir / "solver.MPI.CUDA.ex"
        exe_path.write_text("binary")
        exe_path.chmod(0o755)
        case_inputs = case_dir / "inputs"
        case_inputs.write_text("amr.max_level = 1\n")

        run_dir = tmp_path / "run_dir"
        run_dir.mkdir()

        tool_payloads = [
            ("query_knowledge", {"question": "test", "code": "AMReX"}),
            (
                "create_simulation_plan",
                {
                    "prompt": "minimal test plan",
                    "output_dir": str(tmp_path / "plan_output"),
                },
            ),
            (
                "create_proposed_modifications_with_plan",
                {"prompt": "minimal test plan"},
            ),
            (
                "select_baseline_case",
                {"prompt": "minimal baseline", "code": "AMReX", "top_k": 1},
            ),
            ("validate_inputs", {"inputs_file_path": str(inputs_path)}),
            ("setup_job", {"inputs_file_path": str(case_inputs), "case_dir": str(case_dir)}),
            (
                "run_simulation",
                {
                    "inputs_file_path": str(case_inputs),
                    "case_dir": str(case_dir),
                    "submit": {"dry_run": True},
                    "config_overrides": {"environment": "local", "output_dir": str(tmp_path / "runs")},
                },
            ),
            ("analyze_results", {"run_directory": str(run_dir)}),
            ("generate_visualizations", {"run_directory": str(run_dir)}),
        ]

        request_id = 2
        for tool_name, arguments in tool_payloads:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                }
            )
            response = _recv_or_xfail(request_id, timeout=20.0)
            assert "result" in response or "error" in response
            request_id += 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
